from __future__ import annotations

from shared.base_agent import Skill


def summarize_context(context: dict) -> str:
    if not context:
        return "No additional context supplied."
    pairs = [f"{key}: {value}" for key, value in context.items()]
    return "\n".join(pairs)


def add_numbers(values: list[float]) -> float:
    return sum(values)


common_skills = [
    Skill(
        name="summarize_context",
        description="Turn a request context dictionary into a readable summary.",
        handler=summarize_context,
    ),
    Skill(
        name="add_numbers",
        description="Add a list of numeric values deterministically.",
        handler=add_numbers,
    ),
]
