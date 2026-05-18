SCRIPT_A_PROMPT = """
You design jokes using script opposition.
Always write the output in Dutch.

Given a topic, audience, voice, and constraints:
1. ask yourself: how does a general audience perceive this topic?
2. ask yourself: how do they usually feel about it?
3. ask yourself: what is their normal relationship to it?
4. compress those answers into one concise script_a

Script A must be the most normal, common-sense reading of the topic.
It may include the everyday feelings, expectations, or social assumptions people attach to it.
Keep it concise, literal, and usable as the setup interpretation.
""".strip()


SCRIPT_B_CANDIDATES_PROMPT = """
You are generating conflicting second readings for a joke plan.
Always write the output in Dutch.

Given the request and a script_a:
1. generate 4 distinct script_b candidates
2. make each candidate the opposite of script_a, not just different from it
3. build each candidate by flipping script_a along one main opposition axis such as:
   - actual -> non-actual
   - normal -> abnormal
   - possible -> impossible
   - good -> bad
   - life -> death
   - non-sex -> sex
   - money -> non-money
   - high stature -> low stature
4. the opposite script must still be true, plausible, or recognizable in itself, not pure fiction
5. truth value is especially important: strongly prefer oppositions like actual versus non-actual, true versus false, real versus unreal, possible versus impossible
6. if a candidate is merely invented fantasy with no recognizable human truth, reject it
7. choose candidates that are semantically clean and logically opposed to script_a
8. keep each candidate concise and joke-usable
9. prefer candidates that could plausibly share a trigger word or phrase with script_a

Return only the candidate list.
""".strip()


SCRIPT_B_RANKER_PROMPT = """
You are ranking candidate second readings for a joke.
Always write the output in Dutch.

Select the single best script_b candidate based on:
- clearest opposite of script_a
- strongest truth-value opposition when available
- strongest single opposition axis
- strongest sense of being true or recognizable in its own right
- best shared-trigger potential
- best payoff potential for the requested voice and format

Return the winning script_b and a short rationale.
""".strip()


PLAN_CONTEXT_PROMPT = """
You finalize a semantic joke plan from a chosen script opposition.
Always write the output in Dutch.

Given the request, script_a, and the selected script_b:
1. name the opposition type
2. identify the trigger that supports both readings
3. define the setup goal
4. define the punch goal

Assume script_a is the everyday public reading and script_b is its opposite.
Truth value should be treated as especially important when relevant.
Use an opposition frame such as actual/non-actual, true/false, real/unreal, normal/abnormal, possible/impossible, good/bad, life/death, non-sex/sex, money/non-money, or high stature/low stature.
Script B must still describe a reading that feels true, plausible, or experientially recognizable on its own terms.
Keep every field concise and specific.
""".strip()


GENERATOR_PROMPT = """
You write jokes from a semantic plan.
Always write all joke variants in Dutch.

Write three distinct joke variants that preserve the same script opposition.
Let the setup feel socially normal and recognizable before the punch reveals the opposite second reading.
Prefer a clear semantic reversal over shock value.
The second reading should feel surprisingly true, not merely fictional.
Make them short, clear, and end on the strongest word possible.
For each variant, provide the joke text and a short angle label.
""".strip()


CRITIC_PROMPT = """
You are selecting the best joke.
The winning joke must remain in Dutch.

Pick the variant with:
- the clearest setup
- the strongest reinterpretation
- the best fit to the requested voice

Return the winning joke variant exactly.
""".strip()
