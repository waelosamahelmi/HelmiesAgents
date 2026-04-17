from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CompressionResult:
    summary: str
    recent_context: str


class ContextCompressor:
    """Deterministic context compression for long sessions.

    This avoids model-token blowups before we add model-native compression.
    """

    def compress(self, messages: list[tuple[str, str]], keep_last: int = 10) -> CompressionResult:
        if len(messages) <= keep_last:
            recent = "\n".join([f"{r}: {c}" for r, c in messages])
            return CompressionResult(summary="", recent_context=recent)

        old = messages[:-keep_last]
        recent = messages[-keep_last:]

        # Simple deterministic summarization by role-bucket and key lines.
        old_lines = [f"{r}: {c}" for r, c in old]
        summary_points = old_lines[:6] + ([f"... ({len(old_lines)-6} more lines)"] if len(old_lines) > 6 else [])
        summary = "Session summary:\n- " + "\n- ".join(summary_points)

        recent_context = "\n".join([f"{r}: {c}" for r, c in recent])
        return CompressionResult(summary=summary, recent_context=recent_context)
