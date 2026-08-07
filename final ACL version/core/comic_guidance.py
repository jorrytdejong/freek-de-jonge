from __future__ import annotations


COMIC_REALIZATION_GUIDANCE = """
Comic validity requirements:
- The result must create an immediate comic payoff, not merely express an insightful or critical idea.
- A serious observation, aphorism, slogan, moral conclusion, or elegant metaphor without a laugh-trigger is invalid.
- Build pressure toward a distinct punchline and place the funniest information as late as possible.
- Do not explain the underlying point after the punchline; stop when the laugh lands.
- Silently consider several punchlines and use the funniest complete realization.
""".strip()


COMIC_SELECTION_GUIDANCE = """
Comic eligibility is non-compensatory. First reject any candidate that:
- reads primarily as an observation, thesis, aphorism, slogan, or serious conclusion
- has no identifiable laugh-trigger or distinct comic payoff
- explains its point instead of landing and stopping
- merely demonstrates the supplied plan or opposition

Among eligible candidates, treat funniness, punchline strength, and performability as
primary. Treat structural fidelity, clarity, topic fit, and originality as secondary.
A structurally cleaner candidate must not defeat a substantially funnier one merely
because its planned mechanism is easier to identify.
""".strip()
