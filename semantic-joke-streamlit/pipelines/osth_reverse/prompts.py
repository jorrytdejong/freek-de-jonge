TARGET_FINAL_PROMPT = """
You design the intended final OSTH analysis for a joke that has not been written yet.
Start from the user's topic, audience, tone, constraints, and any revision feedback.
Specify the first script, the incongruity, the second resolving script, the script opposition, required world knowledge, and the intended explanation.
Always write creative fields in Dutch. Do not write the joke yet. Do not explain outside the schema.
""".strip()


OPPOSITION_PROMPT = """
You turn an intended final analysis into a precise target script opposition.
Create two script candidates with participants, preconditions, expected events, goals, and planned evidence.
The first script should dominate the setup. The second script should resolve the punchline.
Always write creative fields in Dutch.
""".strip()


INCONGRUITY_PROMPT = """
You design the central incongruous event for the target joke.
The event must violate the first script but become coherent under the second script.
Use event ids and planned text that can later be realized as a punchline or punchline-adjacent sentence.
Always write creative fields in Dutch.
""".strip()


SCRIPT_PROMPT = """
You refine the target scripts into a ScriptAnalysis plan for joke generation.
The primary script should support misdirection. Alternative scripts should include the intended resolving script and any plausible distractors.
Always write creative fields in Dutch.
""".strip()


DISCOURSE_PROMPT = """
You build a discourse-level TMR plan for the unwritten joke.
Create entities, planned selected sentence TMRs, discourse relations, and unresolved ambiguities that should remain until the punchline.
Always write creative fields in Dutch.
""".strip()


TMR_PROMPT = """
You create sentence-level TMR hypotheses for a joke that has not been written yet.
Each TMR should be a semantic target for a future sentence. Include setup-compatible readings and the punchline reinterpretation.
Always write creative fields in Dutch.
""".strip()


CONSTRAINT_PROMPT = """
You derive semantic constraints that the generated joke must satisfy.
Include role restrictions, defaults, preconditions, expected effects, and constraints that prevent revealing the second script too early.
Always write creative fields in Dutch.
""".strip()


LEXICON_ONTOLOGY_PROMPT = """
You choose the local lexicon, ontology patch, and planned surface cues for the joke.
Select words and concepts that support the first script in the setup and activate the second script at the punchline.
Keep all commitments compatible with the user's constraints and forbidden content.
Always write creative fields in Dutch.
""".strip()


SURFACE_PLAN_PROMPT = """
You create a surface realization plan for the joke.
Plan sentence ids, discourse roles, speakers, semantic functions, cues to include, things to avoid, and syntactic shapes.
Do not write the finished joke yet. Always write creative fields in Dutch.
""".strip()


DRAFT_PROMPT = """
You write the actual joke from the typed semantic plan.
Keep the first script dominant until the punchline. Use the planned cues naturally. Make the punchline activate the second script.
Respect the requested tone, length, audience context, taboo level, and forbidden content.
The joke text and punchline must be in Dutch.
""".strip()


VERIFY_PROMPT = """
You verify whether the generated joke realizes the intended OSTH mechanism.
Judge whether the first script, second script, incongruity, and opposition are recoverable from the surface text.
Return concrete revision advice if the mechanism is weak.
Always write explanatory fields in Dutch.
""".strip()
