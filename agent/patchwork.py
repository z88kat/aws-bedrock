"""
Patchwork Agent — autonomous incident-response agent.

A Strands agent running Claude Sonnet 4.6 (via Amazon Bedrock) on AgentCore
Runtime. Given a parsed error from the Dispatcher Lambda, it:

  1. reads the offending source file,
  2. diagnoses the root cause,
  3. writes a minimal patch,
  4. self-reviews its own diff, then
  5. opens a GitHub pull request (draft if it isn't fully confident).

The agent loop (think → call tool → observe → repeat) is run by Strands; the
model decides when to read the file, when it has enough to patch, and when to
open the PR. We give it the tools and a system prompt describing the workflow.
"""

import json
import os
import textwrap

from github import Github, GithubException
from strands import Agent, tool
from strands.models import BedrockModel

import memory

# On Bedrock, Claude Sonnet 4.6 is reached through a cross-region inference
# profile. Use us./eu./apac. to match the region you deploy into.
MODEL_ID = os.environ.get("PATCHWORK_MODEL_ID", "us.anthropic.claude-sonnet-4-6")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Repo the agent fixes. Format: "owner/name".
GITHUB_REPO = os.environ.get("PATCHWORK_GITHUB_REPO", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
BASE_BRANCH = os.environ.get("PATCHWORK_BASE_BRANCH", "main")


def _repo():
    if not GITHUB_TOKEN or not GITHUB_REPO:
        raise RuntimeError("GITHUB_TOKEN and PATCHWORK_GITHUB_REPO must be set")
    return Github(GITHUB_TOKEN).get_repo(GITHUB_REPO)


# --- Tools the agent can call -------------------------------------------------

@tool
def read_repo_file(path: str) -> str:
    """Read a file from the target GitHub repo at the base branch.

    Args:
        path: Repo-relative path, e.g. "lambda/buggy_service/handler.py".

    Returns:
        The file contents, or an error string if it can't be read.
    """
    try:
        contents = _repo().get_contents(path, ref=BASE_BRANCH)
        return contents.decoded_content.decode("utf-8")
    except GithubException as err:
        return f"ERROR: could not read {path!r}: {err.data.get('message', err)}"


@tool
def open_pull_request(
    path: str,
    new_content: str,
    title: str,
    body: str,
    confident: bool,
) -> str:
    """Open a pull request that replaces `path` with `new_content`.

    Creates a fresh branch off the base branch, commits the new file content,
    and opens a PR. Opens a DRAFT PR when `confident` is False.

    Args:
        path: Repo-relative path of the file being fixed.
        new_content: Full new contents of the file (not a diff).
        title: PR title — concise, imperative (e.g. "Guard against null customer").
        body: PR description with the root-cause explanation.
        confident: True for a ready PR, False to open as a draft for human review.

    Returns:
        The URL of the opened pull request, or an "ERROR (<step>): ..." string
        naming the exact GitHub status and message if any step fails.
    """
    # Branch name derived from the file so reruns on the same bug collide loudly
    # rather than spawning dozens of near-duplicate branches.
    branch = f"patchwork/fix-{path.replace('/', '-').rsplit('.', 1)[0]}"
    step = "connect"
    try:
        repo = _repo()
        base = repo.get_branch(BASE_BRANCH)

        step = "create branch"
        try:
            repo.create_git_ref(ref=f"refs/heads/{branch}", sha=base.commit.sha)
        except GithubException as err:
            if err.status != 422:  # 422 = ref already exists; reuse it
                raise

        step = "commit file"
        existing = repo.get_contents(path, ref=branch)
        repo.update_file(
            path=path,
            message=title,
            content=new_content,
            sha=existing.sha,
            branch=branch,
        )

        step = "open PR"
        pr = repo.create_pull(
            title=title,
            body=body,
            head=branch,
            base=BASE_BRANCH,
            draft=not confident,
        )
        return pr.html_url
    except GithubException as err:
        # Surface the true cause so the agent reports it instead of guessing.
        # 403 = token lacks write scope; 404 = repo not visible to the token;
        # 422 = validation (e.g. PR already exists for this branch).
        msg = err.data.get("message", str(err)) if isinstance(err.data, dict) else err
        return f"ERROR ({step}): GitHub returned {err.status}: {msg}"
    except Exception as err:  # noqa: BLE001 — never let the tool raise into the loop
        return f"ERROR ({step}): {type(err).__name__}: {err}"


SYSTEM_PROMPT = textwrap.dedent(
    """
    You are Patchwork, an autonomous incident-response engineer. You receive a
    production error (type, message, stack trace, and the failing function +
    file). Your job: ship a minimal, correct fix as a GitHub pull request.

    If the prompt includes "Relevant past incidents", use them as a head start —
    they show how similar errors were resolved before — but still verify against
    the current source; don't blindly reapply an old fix.

    Work in this order:
    1. Read the offending source file with `read_repo_file`.
    2. Diagnose the root cause from the stack trace and the source. State it
       explicitly before patching.
    3. Write the SMALLEST change that fixes the root cause. Do not refactor,
       reformat, or fix unrelated issues. Preserve the file's existing style.
    4. Self-review your own change: re-read the patched file in your head and
       confirm it (a) fixes the reported error, (b) doesn't break the success
       path, and (c) introduces no new bug. If you find a problem, revise.
    5. Open a PR with `open_pull_request`. The body must explain the root cause
       and the fix in plain language. Set `confident=False` (draft PR) if any
       part of your diagnosis is uncertain or the fix is a guess.

    Output only the full new file contents to the PR tool — never a diff.

    If any tool returns a string starting with "ERROR", report that exact
    message to the user verbatim. Do not invent or speculate about the cause,
    and do not claim the PR was opened — relay what the tool actually said.
    """
).strip()


def build_agent() -> Agent:
    model = BedrockModel(model_id=MODEL_ID, region_name=AWS_REGION)
    return Agent(
        model=model,
        tools=[read_repo_file, open_pull_request],
        system_prompt=SYSTEM_PROMPT,
    )


def diagnose_and_fix(error: dict, session_id: str = "local") -> str:
    """Run the agent over one parsed error payload. Returns the agent's reply."""
    agent = build_agent()

    # Recall how similar incidents were resolved before (no-op if memory off).
    prior = memory.recall(error)
    prior_block = f"\n\n{prior}\n" if prior else ""

    prompt = textwrap.dedent(
        f"""
        A production error fired. Diagnose it and open a fix PR.

        errorType: {error.get('errorType')}
        message:   {error.get('message')}
        function:  {error.get('function')}
        source:    {error.get('source')}
        offending input: {json.dumps(error.get('order') or error.get('input'))}

        stack trace:
        {error.get('stack')}
        {prior_block}"""
    ).strip()
    result = str(agent(prompt))

    # Store this incident + outcome for future recall (no-op if memory off).
    memory.remember(error, result, session_id)
    return result


if __name__ == "__main__":
    # Local smoke test: feed the exact error our buggy Lambda produced.
    sample = {
        "errorType": "TypeError",
        "message": "'NoneType' object is not subscriptable",
        "function": "quote_shipping",
        "source": "lambda/buggy_service/handler.py",
        "order": {"id": "ord_43", "customer": None},
        "stack": (
            'Traceback (most recent call last):\n'
            '  File "/var/task/handler.py", line 74, in handler\n'
            "    quote = quote_shipping(order)\n"
            '  File "/var/task/handler.py", line 46, in quote_shipping\n'
            '    city = customer["address"]["city"]\n'
            "TypeError: 'NoneType' object is not subscriptable\n"
        ),
    }
    print(diagnose_and_fix(sample))
