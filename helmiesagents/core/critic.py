from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CriticResult:
    score: float
    pass_gate: bool
    feedback: str


class ResponseCritic:
    """Lightweight deterministic critic loop.

    This intentionally avoids extra LLM calls for predictability and cost.
    """

    def evaluate(self, *, user_message: str, response_text: str, required_keywords: list[str]) -> CriticResult:
        text = (response_text or "").strip()
        if not text:
            return CriticResult(score=0.0, pass_gate=False, feedback="Empty response")

        score = 0.4  # non-empty baseline

        # reward lexical overlap between request and response
        q_tokens = [t for t in user_message.lower().split() if len(t) > 3]
        if q_tokens:
            overlap = sum(1 for t in q_tokens if t in text.lower())
            score += min(0.3, overlap / max(1, len(q_tokens)) * 0.3)

        missing = [k for k in required_keywords if k.lower() not in text.lower()]
        if missing:
            score -= min(0.4, 0.15 * len(missing))
        else:
            # explicit reward for satisfying required lexical anchors
            score += 0.35

        # reward actionable structure
        if any(x in text for x in ["\n- ", "1.", "2."]):
            score += 0.1

        score = max(0.0, min(1.0, score))
        pass_gate = not missing and score >= 0.7

        if pass_gate:
            feedback = "Looks good"
        elif missing:
            feedback = f"Missing required keywords: {', '.join(missing)}"
        else:
            feedback = "Low confidence response; improve specificity and structure"

        return CriticResult(score=score, pass_gate=pass_gate, feedback=feedback)

    def required_keywords_from_prompt(self, user_message: str) -> list[str]:
        q = user_message.lower()
        required: list[str] = []
        if "time" in q:
            required.append("time")
        if "file" in q:
            required.append("file")
        if "list" in q and "file" in q:
            required.append("files")
        if "ingest" in q:
            required.append("ingest")
        return required
