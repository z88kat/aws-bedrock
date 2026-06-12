# Patchwork — autonomous incident-response agent

A real error triggers an agent that diagnoses it, writes a fix, and opens a
GitHub PR. The brain is a single [Strands](https://strandsagents.com) agent
running Claude Sonnet 4.6 on **Amazon Bedrock AgentCore Runtime**.

## How it works

```
buggy-service ──throws──▶ CloudWatch logs ──filter──▶ Dispatcher Lambda
   (Lambda)                                                  │
                                              invoke_agent_runtime
                                                              ▼
                                          Patchwork agent (Strands + Claude)
                                              │ read source · diagnose
                                              │ patch · self-review
                                              ▼
                                          GitHub pull request
```

1. **buggy-service** fails on bad input and logs a structured `quote.error`.
2. A **CloudWatch subscription filter** matches that line and invokes the
   **Dispatcher Lambda**, which parses the error and calls the agent.
3. The **Patchwork agent** reads the offending source, diagnoses the root
   cause, writes a minimal fix, self-reviews its own diff, and opens a PR
   (draft if it isn't fully confident).

## Components

### buggy-service (Lambda)

A small Python app with a real, diagnosable bug. See
[lambda/buggy_service/handler.py](lambda/buggy_service/handler.py).

It computes a shipping quote for an incoming order. The bug: it assumes every
order has a `customer.address`, but guest checkouts send `"customer": null`,
so the handler raises `TypeError: 'NoneType' object is not subscriptable` and
logs the traceback as structured JSON.

```bash
# Normal order → 200 with a quote
python -c 'from lambda.buggy_service.handler import handler; \
  print(handler({"id":"ord_42","customer":{"address":{"city":"London"}}}, None))'

# Guest checkout → raises, logs the traceback (the agent's input signal)
python -c 'from lambda.buggy_service.handler import handler; \
  handler({"id":"ord_43","customer":None}, None)'
```

The error log entry includes `errorType`, `message`, `source`, `function`,
`stack`, and the offending `order` — everything the agent needs to trace the
failure back to the source and propose a fix.

### Dispatcher Lambda

[lambda/dispatcher/handler.py](lambda/dispatcher/handler.py) — invoked by the
CloudWatch subscription filter. Decodes the (gzipped) log payload, extracts the
`quote.error` JSON, and forwards it to the agent via `invoke_agent_runtime`.

### Patchwork agent (Strands on AgentCore)

The single agent that diagnoses errors, writes the fix, self-reviews, and opens
the PR.

- [agent/patchwork.py](agent/patchwork.py) — the Strands agent: Claude Sonnet
  4.6 via Bedrock, plus `read_repo_file` and `open_pull_request` tools and the
  diagnose → patch → self-review → PR workflow.
- [agent/runtime.py](agent/runtime.py) — the AgentCore Runtime entrypoint
  (`agentcore launch` packages this).

Deploy:

```bash
cd agent && pip install -r requirements.txt
agentcore configure --entrypoint runtime.py

# One-time: create the memory store, capture its id
MEMORY_ID=$(python provision_memory.py)

agentcore launch \
  --env GITHUB_TOKEN=github_pat_xxxx \
  --env PATCHWORK_GITHUB_REPO=owner/repo \
  --env PATCHWORK_MEMORY_ID=$MEMORY_ID
```

The GitHub token needs **Contents: Read and write** and **Pull requests: Read
and write** on the target repo. Memory is optional — omit `PATCHWORK_MEMORY_ID`
and the agent runs the same, just without cross-incident recall.

## Project layout

```
agent/
  patchwork.py          Strands agent — diagnose, patch, self-review, open PR
  runtime.py            AgentCore Runtime entrypoint
  memory.py             AgentCore Memory — recall/store past incidents
  provision_memory.py   one-time memory-store setup
  requirements.txt
lambda/
  buggy_service/
    handler.py        the buggy Lambda — throws on bad input, logs traceback
  dispatcher/
    handler.py        CloudWatch → invoke_agent_runtime bridge
PLAN.md               the demo plan
```

## Roadmap

- [x] buggy-service Lambda that emits a real, diagnosable error
- [x] Strands agent on AgentCore Runtime (Claude Sonnet 4.6)
- [x] agent reads source, diagnoses, self-reviews, opens a GitHub PR
- [x] error → agent trigger (CloudWatch subscription filter + Dispatcher Lambda)
- [x] AgentCore Memory — recall past incidents for faster repeat fixes
- [ ] adversarial self-review as a separate verification pass
