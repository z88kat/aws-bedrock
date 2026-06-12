"""
Dispatcher Lambda — the bridge between a real error and the Patchwork agent.

A CloudWatch Logs subscription filter on the buggy-service log group invokes
this function whenever a matching log line appears. We:

  1. decode the (gzipped, base64) subscription payload,
  2. pull the structured `quote.error` JSON out of each matching log line,
  3. invoke the Patchwork agent on AgentCore Runtime with that error.

The agent already knows which repo to patch (via its own env config); the
error record carries the failing function + source file, so the dispatcher
just parses and forwards.
"""

import base64
import gzip
import json
import os
import uuid

import boto3

AGENT_RUNTIME_ARN = os.environ["PATCHWORK_AGENT_RUNTIME_ARN"]
AGENT_QUALIFIER = os.environ.get("PATCHWORK_AGENT_QUALIFIER", "DEFAULT")

agentcore = boto3.client("bedrock-agentcore")


def _extract_json_records(message: str) -> list[dict]:
    """Pull JSON objects out of a CloudWatch log line.

    Lambda prefixes log lines with `[ERROR]\\t<ts>\\t<reqid>\\t` before our
    JSON, so we scan for the first `{` and json-decode from there.
    """
    start = message.find("{")
    if start == -1:
        return []
    try:
        return [json.loads(message[start:])]
    except json.JSONDecodeError:
        return []


def handler(event, context):
    raw = base64.b64decode(event["awslogs"]["data"])
    payload = json.loads(gzip.decompress(raw))

    dispatched = 0
    for log_event in payload.get("logEvents", []):
        for record in _extract_json_records(log_event["message"]):
            if record.get("event") != "quote.error":
                continue

            # runtimeSessionId must be 33-128 chars; a uuid4 hex (32) + prefix fits.
            session_id = f"patchwork-{uuid.uuid4().hex}"
            agentcore.invoke_agent_runtime(
                agentRuntimeArn=AGENT_RUNTIME_ARN,
                qualifier=AGENT_QUALIFIER,
                runtimeSessionId=session_id,
                payload=json.dumps({"error": record}).encode("utf-8"),
            )
            dispatched += 1
            print(
                json.dumps(
                    {
                        "event": "dispatch",
                        "errorType": record.get("errorType"),
                        "function": record.get("function"),
                        "session": session_id,
                    }
                )
            )

    return {"dispatched": dispatched}
