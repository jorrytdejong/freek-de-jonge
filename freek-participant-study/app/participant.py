"""Participant profile rules independent of the Streamlit interface."""

from __future__ import annotations

from dataclasses import dataclass

MINIMUM_AGE = 1
MAXIMUM_AGE = 120
MINIMUM_FAMILIARITY = 1
MAXIMUM_FAMILIARITY = 5


class ProfileValidationError(ValueError):
    """Raised with all participant-profile validation messages."""

    def __init__(self, messages: list[str]) -> None:
        self.messages = tuple(messages)
        super().__init__("; ".join(messages))


@dataclass(frozen=True)
class ParticipantProfile:
    age: int
    freek_familiarity: int
    consent: bool


def validate_profile(
    *,
    age: int | None,
    freek_familiarity: int | None,
    consent: bool,
) -> ParticipantProfile:
    """Validate required participant input and return normalized values."""
    messages: list[str] = []

    if age is None:
        messages.append("Vul je leeftijd in.")
    elif isinstance(age, bool) or not isinstance(age, int):
        messages.append("Vul je leeftijd in hele jaren in.")
    elif not MINIMUM_AGE <= age <= MAXIMUM_AGE:
        messages.append(
            f"Vul een leeftijd tussen {MINIMUM_AGE} en {MAXIMUM_AGE} jaar in."
        )

    if freek_familiarity is None:
        messages.append(
            "Geef aan hoe goed je het werk van Freek de Jonge kent."
        )
    elif (
        isinstance(freek_familiarity, bool)
        or not isinstance(freek_familiarity, int)
        or not MINIMUM_FAMILIARITY
        <= freek_familiarity
        <= MAXIMUM_FAMILIARITY
    ):
        messages.append("Kies voor bekendheid een waarde van 1 tot en met 5.")

    if not consent:
        messages.append("Geef toestemming om vrijwillig deel te nemen.")

    if messages:
        raise ProfileValidationError(messages)

    assert age is not None
    assert freek_familiarity is not None
    return ParticipantProfile(
        age=age,
        freek_familiarity=freek_familiarity,
        consent=True,
    )

