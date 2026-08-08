# Semantic Joke Streamlit App

This is a self-contained Streamlit version of the Semantic Joke pipelines.
It includes its own prompts, schemas, model selection, token usage, cost calculation, and duration tracking.

## Architecture

```text
semantic-joke-streamlit/
  streamlit_app.py
  schemas.py
  core/
    llm.py
    pipeline.py
    pricing.py
    registry.py
    storage.py
    usage.py
  data/
    jokes.sqlite3
  pipelines/
    semantic_steps/
      pipeline.py
      prompts.py
    single_prompt/
      pipeline.py
      prompts.py
    osth_reverse/
      pipeline.py
      models.py
      prompts.py
    gtvh/
      pipeline.py
      models.py
      prompts.py
```

Each pipeline lives in its own folder and exports a `PIPELINE` definition plus a `run(request, client)` function.
To add another pipeline, create `pipelines/<new_pipeline>/pipeline.py`, add its prompts next to it, then register its `PIPELINE` in `core/registry.py`.

## Run

From the project root:

```bash
source ~/venvs/freek-de-jonge-local/bin/activate
pip install -r semantic-joke-streamlit/requirements.txt
streamlit run semantic-joke-streamlit/streamlit_app.py
```

## Smoke Test

```bash
PYTHONDONTWRITEBYTECODE=1 python semantic-joke-streamlit/smoke_test.py
```

## Configuration

`OPENAI_API_KEY` is required. You can provide it in one of three ways:

- Export it in your shell before starting Streamlit.
- Add it to Streamlit secrets as `OPENAI_API_KEY`.
- Enter it in the sidebar password field when the app starts.

The sidebar model selector writes to `OPENAI_MODEL` before each generation, so the cost estimate follows the selected model.
The pipeline selector is a menu so you can choose one pipeline at a time against the same request.
Successful generations are saved automatically to `semantic-joke-streamlit/data/jokes.sqlite3`.

Current pipelines:

- `Script Opposition Pipeline`: separate structured calls for each semantic stage.
- `Single Prompt`: one structured call that performs the same semantic stages internally.
- `OStH Reverse Pipeline`: notebook-inspired reverse-OStH pipeline with typed stages for target analysis, opposition, TMR planning, semantic constraints, surface realization, draft, and verification. This pipeline makes several model calls, so its price tag can be higher and is shown in Generation Stats.
- `GTVH Pipeline`: seven-stage pipeline copied from the GTVH app structure: situation, script opposition, logical mechanism, narrative strategy, language drafts, target decision, and refinement. Its multi-call price tag is shown in Generation Stats.

## Output

The report shows:

- Selected pipeline report
- Best joke
- Generation stats: model, input tokens, output tokens, total tokens, estimated cost, duration
- Semantic plan
- Script B candidates and rationale
- Joke variants
- Saved joke history with search and detail inspection
- Optional raw JSON

## Storage Test

```bash
PYTHONDONTWRITEBYTECODE=1 python semantic-joke-streamlit/storage_test.py
```
