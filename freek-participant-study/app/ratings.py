"""Display mapping and validation for one joke-group response."""

from __future__ import annotations

from dataclasses import dataclass

from app.assignment import AssignedGroup
from app.stimuli import JokeGroup

DISPLAY_LABELS = tuple("ABCDEFGH")
MINIMUM_RATING = 1
MAXIMUM_RATING = 5


class RatingConfigurationError(ValueError):
    """Raised when an assignment cannot be mapped to the stimulus group."""


class GroupRatingValidationError(ValueError):
    """Raised with all missing or invalid group-rating messages."""

    def __init__(self, messages: list[str]) -> None:
        self.messages = tuple(messages)
        super().__init__("; ".join(messages))


@dataclass(frozen=True)
class DisplayedVariant:
    display_label: str
    display_position: int
    variant_id: str
    text: str


@dataclass(frozen=True)
class VariantRating:
    display_label: str
    display_position: int
    variant_id: str
    funniness: int
    freek_similarity: int


@dataclass(frozen=True)
class GroupRatingResponse:
    group_id: str
    ratings: tuple[VariantRating, ...]
    comment: str


def build_displayed_variants(
    assigned_group: AssignedGroup,
    joke_group: JokeGroup,
) -> tuple[DisplayedVariant, ...]:
    """Map deterministic assignment order to neutral labels A through H."""
    variants_by_id = {variant.variant_id: variant for variant in joke_group.variants}
    assigned_ids = set(assigned_group.variant_ids)
    available_ids = set(variants_by_id)
    if assigned_group.group_id != joke_group.group_id:
        raise RatingConfigurationError(
            f"Toewijzing {assigned_group.group_id} hoort niet bij "
            f"{joke_group.group_id}."
        )
    if len(assigned_group.variant_ids) != len(DISPLAY_LABELS):
        raise RatingConfigurationError(
            f"Groep {assigned_group.group_id} heeft "
            f"{len(assigned_group.variant_ids)} toegewezen varianten; "
            f"verwacht {len(DISPLAY_LABELS)}."
        )
    if assigned_ids != available_ids:
        raise RatingConfigurationError(
            f"Toegewezen varianten voor {assigned_group.group_id} "
            "komen niet overeen met het stimulusbestand."
        )

    return tuple(
        DisplayedVariant(
            display_label=DISPLAY_LABELS[position - 1],
            display_position=position,
            variant_id=variant_id,
            text=variants_by_id[variant_id].text,
        )
        for position, variant_id in enumerate(
            assigned_group.variant_ids,
            start=1,
        )
    )


def validate_group_response(
    *,
    group_id: str,
    displayed_variants: tuple[DisplayedVariant, ...],
    raw_ratings: dict[str, dict[str, int | None]],
    comment: str,
) -> GroupRatingResponse:
    """Require both 1-5 ratings for every displayed variant."""
    messages: list[str] = []
    ratings: list[VariantRating] = []

    for variant in displayed_variants:
        values = raw_ratings.get(variant.variant_id, {})
        funniness = values.get("funniness")
        freek_similarity = values.get("freek_similarity")

        if funniness is None:
            messages.append(
                f"Versie {variant.display_label}: kies een score voor Grappigheid."
            )
        elif (
            isinstance(funniness, bool)
            or not isinstance(funniness, int)
            or not MINIMUM_RATING <= funniness <= MAXIMUM_RATING
        ):
            messages.append(
                f"Versie {variant.display_label}: Grappigheid moet tussen "
                "1 en 5 liggen."
            )

        if freek_similarity is None:
            messages.append(
                f"Versie {variant.display_label}: kies een score voor "
                "Lijkt op Freek de Jonge."
            )
        elif (
            isinstance(freek_similarity, bool)
            or not isinstance(freek_similarity, int)
            or not MINIMUM_RATING <= freek_similarity <= MAXIMUM_RATING
        ):
            messages.append(
                f"Versie {variant.display_label}: Lijkt op Freek de Jonge "
                "moet tussen 1 en 5 liggen."
            )

        if (
            isinstance(funniness, int)
            and not isinstance(funniness, bool)
            and MINIMUM_RATING <= funniness <= MAXIMUM_RATING
            and isinstance(freek_similarity, int)
            and not isinstance(freek_similarity, bool)
            and MINIMUM_RATING <= freek_similarity <= MAXIMUM_RATING
        ):
            ratings.append(
                VariantRating(
                    display_label=variant.display_label,
                    display_position=variant.display_position,
                    variant_id=variant.variant_id,
                    funniness=funniness,
                    freek_similarity=freek_similarity,
                )
            )

    if messages:
        raise GroupRatingValidationError(messages)

    return GroupRatingResponse(
        group_id=group_id,
        ratings=tuple(ratings),
        comment=comment.strip(),
    )
