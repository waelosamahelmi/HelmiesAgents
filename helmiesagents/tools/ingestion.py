from __future__ import annotations

from pathlib import Path


def to_markdown(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))

    ext = p.suffix.lower()
    content = (
        p.read_text(errors="ignore")
        if ext in {".txt", ".md", ".py", ".json", ".yaml", ".yml", ".csv"}
        else ""
    )

    if not content:
        return {
            "path": str(p),
            "markdown": (
                f"# File: {p.name}\n\n"
                "Binary or unsupported text format for direct conversion in core runtime."
            ),
            "note": "Install markitdown for advanced office/pdf conversion in next phase.",
        }

    md = f"# File: {p.name}\n\n```\n{content[:30000]}\n```"
    return {"path": str(p), "markdown": md}
