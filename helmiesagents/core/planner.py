from __future__ import annotations


def make_plan(user_message: str) -> list[str]:
    msg = user_message.strip()
    if not msg:
        return ["Clarify objective"]

    plan = [
        "Clarify objective and constraints",
        "Identify required tools and data",
        "Execute tasks in smallest verifiable increments",
        "Validate outputs and summarize results",
    ]

    if "build" in msg.lower() or "create" in msg.lower():
        plan.insert(2, "Generate implementation skeleton and iterate with tests")
    if "research" in msg.lower() or "analyze" in msg.lower():
        plan.insert(2, "Collect sources and synthesize findings")

    return plan
