"""
AgentCore Runtime entrypoint for the Patchwork agent.

`agentcore launch` packages this into a managed runtime that the Dispatcher
Lambda invokes via `bedrock-agentcore`'s invoke_agent_runtime. The runtime
passes the error payload as `payload`; we hand it to the Strands agent and
return the result.
"""

import uuid

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from patchwork import diagnose_and_fix

app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload: dict) -> dict:
    # The Dispatcher sends the parsed error directly, or wrapped under "error".
    error = payload.get("error", payload)
    # Session id groups this incident's events in AgentCore Memory.
    session_id = f"patchwork-{uuid.uuid4().hex}"
    reply = diagnose_and_fix(error, session_id=session_id)
    return {"result": reply}


if __name__ == "__main__":
    app.run()
