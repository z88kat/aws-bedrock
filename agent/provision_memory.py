"""
One-time provisioning for Patchwork's AgentCore Memory store.

Creates a memory resource with a semantic strategy so incidents are recalled by
similarity (a TypeError in `quote_shipping` surfaces past TypeErrors in the same
area, not just byte-identical ones). Run once, then set the printed id as
PATCHWORK_MEMORY_ID on the agent runtime:

    python provision_memory.py
    agentcore launch --env PATCHWORK_MEMORY_ID=<printed id> ...

Safe to re-run — it looks up an existing store by name before creating one.
"""

import os

from bedrock_agentcore.memory import MemoryClient

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
MEMORY_NAME = "patchwork-incidents"


def main() -> None:
    client = MemoryClient(region_name=AWS_REGION)

    for existing in client.list_memories():
        if existing.get("name") == MEMORY_NAME:
            print(existing["id"])
            return

    memory = client.create_memory_and_wait(
        name=MEMORY_NAME,
        description="Past incidents and their fixes, for the Patchwork agent.",
        strategies=[
            {
                "semanticMemoryStrategy": {
                    "name": "incidentFixes",
                    "namespaces": ["patchwork/incidents/{actorId}"],
                }
            }
        ],
    )
    print(memory["id"])


if __name__ == "__main__":
    main()
