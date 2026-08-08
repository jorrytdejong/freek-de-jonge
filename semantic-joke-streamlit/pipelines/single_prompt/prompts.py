SINGLE_PROMPT_PIPELINE_PROMPT = """
You execute the complete semantic joke pipeline in one structured call.
Always write all creative fields in Dutch.

Use the user request as the only source of topic, audience, voice, format, and constraints.
Work through these stages internally, then return only the structured output:

1. Script A
   - Ask how a general audience perceives the topic.
   - Ask how they usually feel about it.
   - Ask what their normal relationship to it is.
   - Compress that into one concise, literal script_a.
   - Script A must be the normal, common-sense setup interpretation.

2. Script B candidate loop
   - Generate 4 distinct script_b candidates.
   - Each script_b must be the opposite of script_a, not merely different.
   - Prefer clean opposition axes such as actual/non-actual, true/false,
     real/unreal, normal/abnormal, possible/impossible, good/bad, life/death,
     non-sex/sex, money/non-money, or high stature/low stature.
   - Each candidate must still feel true, plausible, or recognizable.
   - Prefer candidates that could share a trigger word or phrase with script_a.

3. Script B ranking
   - Select the best candidate using semantic clarity, truth-value opposition,
     a single strong opposition axis, shared-trigger potential, and payoff.
   - The selected script_b must become plan.script_b.
   - Provide a concise rationale for the choice.

4. Semantic plan
   - Derive opposition_type, trigger, setup_goal, and punch_goal only after
     choosing script_b.
   - Keep every field concise and specific.

5. Joke generation
   - Write 3 distinct joke variants that preserve the same script opposition.
   - Let the setup feel socially normal before the punch reveals script_b.
   - Prefer a clear semantic reversal over shock value.
   - Make each joke short, clear, and end on a strong word.
   - Include a short angle label for each variant.

6. Critic selection
   - Pick the variant with the clearest setup, strongest reinterpretation,
     and best fit to the requested voice.
   - Return best_joke as one of the generated variants exactly.

Do not expose hidden chain-of-thought. Only return the requested structured fields.
""".strip()
