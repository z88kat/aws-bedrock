"""
AgentCore Memory layer for Patchwork.

Gives the agent long-term recall across incidents: when a similar error has
been seen before, the prior diagnosis + fix are surfaced into the prompt so a
repeat (or near-repeat) gets a faster, context-aware fix.

Design: memory is an *enhancement, not a dependency*. If `PATCHWORK_MEMORY_ID`
is unset, or the SDK/network call fails, every function here is a safe no-op —
the agent still diagnoses and fixes exactly as it would without memory. A
flaky memory store must never block shipping a fix.

Provision the memory resource once with `provision_memory.py`, then set the
returned id as PATCHWORK_MEMORY_ID on the runtime.
"""

import os

MEMORY_ID = os.environ.get("PATCHWORK_MEMORY_ID", "")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# One logical agent writing/reading the store; namespace matches the strategy
# template in provision_memory.py (.../{actorId}).
ACTOR_ID = "patchwork"
NAMESPACE = f"patchwork/incidents/{ACTOR_ID}"


def _client():
    # Imported lazily so the agent runs even if the memory extra isn't present.
    from bedrock_agentcore.memory import MemoryClient

    return MemoryClient(region_name=AWS_REGION)


def signature(error: dict) -> str:
    """A short, stable key for an incident — what makes two errors 'the same'."""
    return " ".join(
        str(error.get(k, "")) for k in ("errorType", "function", "source", "message")
    ).strip()


def recall(error: dict, top_k: int = 3) -> str:
    """Return relevant past incidents as prompt context, or "" if none/disabled."""
    if not MEMORY_ID:
        return ""
    try:
        memories = _client().retrieve_memories(
            memory_id=MEMORY_ID,
            namespace=NAMESPACE,
            query=signature(error),
            top_k=top_k,
        )
    except Exception as err:  # noqa: BLE001 — never let recall block the fix
        print(f"[memory] recall skipped: {type(err).__name__}: {err}")
        return ""

    notes = []
    for m in memories or []:
        text = m.get("content", {}).get("text") if isinstance(m, dict) else None
        if text:
            notes.append(f"- {text}")
    if not notes:
        return ""
    return "Relevant past incidents and how they were resolved:\n" + "\n".join(notes)


def remember(error: dict, outcome: str, session_id: str) -> None:
    """Store this incident + the agent's result for future recall. No-op if disabled."""
    if not MEMORY_ID:
        return
    try:
        _client().create_event(
            memory_id=MEMORY_ID,
            actor_id=ACTOR_ID,
            session_id=session_id,
            messages=[
                (f"Incident: {signature(error)}", "USER"),
                (f"Resolution: {outcome}", "ASSISTANT"),
            ],
        )
    except Exception as err:  # noqa: BLE001 — storing is best-effort
        print(f"[memory] remember skipped: {type(err).__name__}: {err}")
