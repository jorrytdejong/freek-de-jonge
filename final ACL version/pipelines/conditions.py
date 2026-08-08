from __future__ import annotations

from core.schemas import PipelineSpec


PIPELINE_SPECS: dict[str, PipelineSpec] = {
    "A1": PipelineSpec(
        code="A1",
        family="baseline",
        style_mode="none",
        name="Baseline Prompt without Freek Style",
        description="Topic-only joke generation without explicit Freek de Jonge guidance.",
    ),
    "A2": PipelineSpec(
        code="A2",
        family="baseline",
        style_mode="freek",
        name="Baseline Prompt with Freek Style",
        description="Topic-only joke generation with explicit Freek de Jonge style guidance.",
    ),
    "B1": PipelineSpec(
        code="B1",
        family="category",
        style_mode="none",
        name="Category-Guided Generation without Freek Style",
        description="Topic plus humor category, without explicit Freek de Jonge guidance.",
    ),
    "B2": PipelineSpec(
        code="B2",
        family="category",
        style_mode="freek",
        name="Category-Guided Generation with Freek Style",
        description="Topic plus humor category, with explicit Freek de Jonge style guidance.",
    ),
    "C1": PipelineSpec(
        code="C1",
        family="script_opposition",
        style_mode="none",
        name="Script-Opposition-Guided Generation without Freek Style",
        description="Internally generated script-opposition pipeline without explicit Freek de Jonge guidance.",
    ),
    "C2": PipelineSpec(
        code="C2",
        family="script_opposition",
        style_mode="freek",
        name="Script-Opposition-Guided Generation with Freek Style",
        description="Internally generated script-opposition pipeline with explicit Freek de Jonge style guidance.",
    ),
    "D1": PipelineSpec(
        code="D1",
        family="category_script",
        style_mode="none",
        name="Category + Script-Opposition Generation without Freek Style",
        description="Category-conditioned internal script-opposition pipeline without explicit Freek de Jonge guidance.",
    ),
    "D2": PipelineSpec(
        code="D2",
        family="category_script",
        style_mode="freek",
        name="Category + Script-Opposition Generation with Freek Style",
        description="Category-conditioned internal script-opposition pipeline with explicit Freek de Jonge style guidance.",
    ),
    "E1": PipelineSpec(
        code="E1",
        family="validated_gtvh",
        style_mode="none",
        name="Validated GTVH Generation without Freek Style",
        description="Theory-gated GTVH pipeline with blind reconstruction and pairwise selection.",
    ),
    "E2": PipelineSpec(
        code="E2",
        family="validated_gtvh",
        style_mode="freek",
        name="Validated GTVH Generation with Freek Style",
        description="Theory-gated GTVH pipeline with Freek guidance, blind reconstruction, and pairwise selection.",
    ),
}


PIPELINE_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2", "D1", "D2", "E1", "E2"]
