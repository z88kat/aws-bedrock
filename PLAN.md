Patchwork - Autonomous Incident-Response Agent
A real error triggers an agent that diagnoses it, writes a fix, and opens a GitHub PR.
One Strands agent on AgentCore Runtime + Memory. That's

buggy-service (Lambda)
Small Python app with a real bug. Throws on bad input → logs the traceback.

CloudWatch Logs → Subscription Filter
Matches ERROR / Exception / Traceback. Fires in seconds.

Dispatcher Lambda
Parses the error, maps the failing function → (repo, file), then calls invoke_agent_runtime.

Patchwork Agent - Strands + Claude Sonnet 4.6
Diagnoses root cause → writes a minimal patch → self-reviews its own diff before opening a PR.

GitHub: Pull Request
The fix, with a root-cause explanation. Opens a draft PR if the agent isn't fully confident.
