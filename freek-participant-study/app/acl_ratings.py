"""Validate the three required ratings and optional comment for one ACL joke."""

from __future__ import annotations

from dataclasses import dataclass

from app.acl_config import RATING_DIMENSIONS, RATING_QUESTIONS

MINIMUM_RATING = 1
MAXIMUM_RATING = 5


class ItemRatingValidationError(ValueError):
    def __init__(self, messages: list[str]) -> None:
        self.messages = tuple(messages)
        super().__init__("; ".join(messages))


@dataclass(frozen=True)
class ItemRatingResponse:
    item_id: str
    display_position: int
    funniness: int
    freek_similarity: int
    coherence: int
    comment: str


def validate_item_response(
    *,
    item_id: str,
    display_position: int,
    raw_ratings: dict[str, int | None],
    comment: str = "",
) -> ItemRatingResponse:
    messages: list[str] = []
    clean: dict[str, int] = {}
    for dimension in RATING_DIMENSIONS:
        value = raw_ratings.get(dimension)
        if value is None:
            messages.append(f"Beantwoord: {RATING_QUESTIONS[dimension]}")
        elif (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not MINIMUM_RATING <= value <= MAXIMUM_RATING
        ):
            messages.append(f"Score voor {dimension} moet tussen 1 en 5 liggen.")
        else:
            clean[dimension] = value
    if messages:
        raise ItemRatingValidationError(messages)
    if not isinstance(comment, str):
        raise ItemRatingValidationError(["De open toelichting is ongeldig."])
    return ItemRatingResponse(
        item_id=item_id,
        display_position=display_position,
        comment=comment.strip(),
        **clean,
    )
