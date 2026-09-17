from __future__ import annotations


FREEK_STYLE_GUIDANCE = """
Use explicit Freek de Jonge style guidance.
Write in Dutch. Aim for politically alert Dutch cabaret: moral seriousness that turns
into irony, compact social observation, verbal precision, dry cynicism, and a punchline
that lands through semantic reversal rather than generic joke wording. Avoid claiming
the text is an authentic Freek de Jonge joke.
""".strip()


C_PIPELINE_FREEK_STYLE_GUIDANCE = """
Use explicit Freek de Jonge style guidance.
Write in Dutch. Aim for politically alert Dutch cabaret.
""".strip()


NEUTRAL_STYLE_GUIDANCE = """
Write in Dutch. Focus on a clear setup, a surprising semantic turn, and a concise final sentence.
""".strip()


def style_guidance(style_mode: str) -> str:
    """Return prompt guidance for a style mode.

    Args:
        style_mode: Style selector, with ``"freek"`` enabling guidance.

    Returns:
        Freek-specific or neutral prompt guidance.
    """
    if style_mode == "freek":
        return FREEK_STYLE_GUIDANCE
    return NEUTRAL_STYLE_GUIDANCE


def c_pipeline_style_guidance(style_mode: str) -> str:
    """Return the deliberately minimal style guidance for C1/C2."""
    if style_mode == "freek":
        return C_PIPELINE_FREEK_STYLE_GUIDANCE
    return NEUTRAL_STYLE_GUIDANCE
