"""Rule text and helpers for the compaction summarizer prompt.

Epistemic stance: compression sheds qualifier words first ("probably", "I suspect", "unconfirmed"),
which either hardens an untested hypothesis into a fact the resumed agent acts on, or drops it and
loses the investigative thread. Asking for stance as an explicit labelled field rather than an inline aside
keeps it through compression (arXiv:2608.06953). Both strings are interpolated into the summarizer
prompt only (never the system prompt or the persisted handoff prefix), so the cached prefix is
untouched; f-string interpolation does not re-parse them, so braces in them are safe.
"""

from typing import Any

UNVERIFIED_SECTION_HEADING = "## Unverified / Working Hypotheses"

EPISTEMIC_STANCE_RULE = (
    "Never restate an uncertain claim (suspicion, hypothesis, unverified inference) as fact: list "
    f'each under {UNVERIFIED_SECTION_HEADING} as "UNVERIFIED: <claim> — <basis>". '
)

UNVERIFIED_HYPOTHESES_SECTION = f"""

{UNVERIFIED_SECTION_HEADING}
[UNVERIFIED: <claim> — <basis so far>, one per line. If none, write "None."]"""

# Variant spellings the summarizer reaches for; each canonicalizes to UNVERIFIED_SECTION_HEADING.
_STANCE_HEADING_VARIANTS = frozenset({
    "unverified / working hypotheses", "unverified hypotheses", "working hypotheses",
    "unverified", "unverified claims",
})


def normalize_stance_section(text: str) -> tuple[str, dict[str, Any]]:
    """Canonicalize the stance heading and measure the section it heads.

    Returns ``(text, report)`` where report is ``{"present", "hypothesis_lines", "explicit_none"}``.
    Counting stops at the next heading so a later section that happens to mention ``UNVERIFIED``
    cannot inflate the number. Pure and single-pass: the summary is measured, never rewritten.
    """
    present = False
    hypothesis_lines = 0
    explicit_none = False
    in_section = False
    out: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip().lower()
            if heading in _STANCE_HEADING_VARIANTS:
                out.append(UNVERIFIED_SECTION_HEADING)
                present = in_section = True
                continue
            in_section = False
        elif in_section:
            body = stripped[2:] if stripped.startswith("- ") else stripped
            if body.upper().startswith("UNVERIFIED:"):
                hypothesis_lines += 1
            elif body.rstrip(".").strip().lower() == "none":
                explicit_none = True
        out.append(line)
    return "\n".join(out), {"present": present, "hypothesis_lines": hypothesis_lines,
                            "explicit_none": explicit_none}


def _today_for_prompt() -> str:
    """Date-only (user tz) for temporal anchoring; "" when the clock fails. Cache-safe: the summary is outside the prefix."""
    try:
        # Date-only granularity matches system_prompt.py:337 (PR #20451) and the user's configured timezone
        # via hermes_time.now(). The compaction summary is a mid-conversation message that is NOT part of
        # the cached prefix, so a date here never affects prompt-cache stability. Resolved defensively — a
        # clock failure must never block compaction.
        from hermes_time import now as _hermes_now
        return _hermes_now().strftime("%Y-%m-%d")
    except Exception:  # pragma: no cover - clock resolution is best-effort
        return ""
