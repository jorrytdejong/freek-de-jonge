"""Load and validate versioned joke stimuli."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from app.config import STUDY_VERSION

EXPECTED_GROUP_COUNT = 12
EXPECTED_VARIANTS_PER_GROUP = 8
REQUIRED_COLUMNS = {
    "study_version",
    "group_id",
    "group_title",
    "variant_id",
    "variant_role",
    "text",
}
EXPECTED_VARIANT_ROLES = {
    "baseline",
    "concise",
    "wordplay",
    "absurdist",
    "social_critique",
    "narrative",
    "self_reflexive",
    "linguistic_turn",
}
GROUP_ID_PATTERN = re.compile(r"^G\d{2}$")
VARIANT_ID_PATTERN = re.compile(r"^(G\d{2})-V(\d{2})$")
DEFAULT_STIMULI_PATH = Path(__file__).resolve().parents[1] / "data" / "jokes.csv"


class StimulusValidationError(ValueError):
    """Raised when the stimulus file violates the study contract."""


@dataclass(frozen=True)
class JokeVariant:
    study_version: str
    group_id: str
    group_title: str
    variant_id: str
    variant_role: str
    text: str


@dataclass(frozen=True)
class JokeGroup:
    group_id: str
    title: str
    variants: tuple[JokeVariant, ...]


def load_stimuli(path: Path = DEFAULT_STIMULI_PATH) -> tuple[JokeGroup, ...]:
    """Load a CSV file and return validated groups in stable file order."""
    if not path.is_file():
        raise StimulusValidationError(f"Stimulusbestand niet gevonden: {path}")

    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        missing_columns = REQUIRED_COLUMNS - fieldnames
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise StimulusValidationError(f"Ontbrekende kolommen: {missing}")

        rows = list(reader)

    return validate_stimuli(rows)


def validate_stimuli(rows: list[dict[str, str]]) -> tuple[JokeGroup, ...]:
    """Validate parsed rows against the fixed pilot-1 stimulus contract."""
    if not rows:
        raise StimulusValidationError("Het stimulusbestand bevat geen rijen.")

    variants_by_group: dict[str, list[JokeVariant]] = {}
    titles_by_group: dict[str, str] = {}
    seen_variant_ids: set[str] = set()

    for row_number, row in enumerate(rows, start=2):
        values = {column: (row.get(column) or "").strip() for column in REQUIRED_COLUMNS}
        empty_columns = [column for column, value in values.items() if not value]
        if empty_columns:
            empty = ", ".join(sorted(empty_columns))
            raise StimulusValidationError(
                f"Rij {row_number} heeft lege verplichte velden: {empty}"
            )

        group_id = values["group_id"]
        variant_id = values["variant_id"]
        if values["study_version"] != STUDY_VERSION:
            raise StimulusValidationError(
                f"Rij {row_number} gebruikt study_version "
                f"{values['study_version']!r}; verwacht {STUDY_VERSION!r}."
            )
        if not GROUP_ID_PATTERN.fullmatch(group_id):
            raise StimulusValidationError(
                f"Rij {row_number} heeft ongeldig group_id {group_id!r}."
            )

        variant_match = VARIANT_ID_PATTERN.fullmatch(variant_id)
        if not variant_match or variant_match.group(1) != group_id:
            raise StimulusValidationError(
                f"Rij {row_number} heeft variant_id {variant_id!r} "
                f"die niet bij {group_id!r} hoort."
            )
        variant_number = int(variant_match.group(2))
        if not 1 <= variant_number <= EXPECTED_VARIANTS_PER_GROUP:
            raise StimulusValidationError(
                f"Rij {row_number} heeft variantnummer {variant_number}; "
                f"verwacht 1-{EXPECTED_VARIANTS_PER_GROUP}."
            )
        if variant_id in seen_variant_ids:
            raise StimulusValidationError(f"Dubbel variant_id: {variant_id}.")
        seen_variant_ids.add(variant_id)

        role = values["variant_role"]
        if role not in EXPECTED_VARIANT_ROLES:
            raise StimulusValidationError(
                f"Rij {row_number} heeft onbekende variant_role {role!r}."
            )

        group_title = values["group_title"]
        existing_title = titles_by_group.setdefault(group_id, group_title)
        if existing_title != group_title:
            raise StimulusValidationError(
                f"Groep {group_id} gebruikt meerdere titels."
            )

        variants_by_group.setdefault(group_id, []).append(
            JokeVariant(
                study_version=values["study_version"],
                group_id=group_id,
                group_title=group_title,
                variant_id=variant_id,
                variant_role=role,
                text=values["text"],
            )
        )

    if len(variants_by_group) != EXPECTED_GROUP_COUNT:
        raise StimulusValidationError(
            f"Verwacht {EXPECTED_GROUP_COUNT} groepen; "
            f"gevonden {len(variants_by_group)}."
        )

    groups: list[JokeGroup] = []
    for group_id, variants in variants_by_group.items():
        if len(variants) != EXPECTED_VARIANTS_PER_GROUP:
            raise StimulusValidationError(
                f"Groep {group_id} bevat {len(variants)} varianten; "
                f"verwacht {EXPECTED_VARIANTS_PER_GROUP}."
            )

        roles = {variant.variant_role for variant in variants}
        if roles != EXPECTED_VARIANT_ROLES:
            missing_roles = EXPECTED_VARIANT_ROLES - roles
            duplicate_count = len(variants) - len(roles)
            details = []
            if missing_roles:
                details.append(f"ontbrekend: {', '.join(sorted(missing_roles))}")
            if duplicate_count:
                details.append(f"dubbele rollen: {duplicate_count}")
            raise StimulusValidationError(
                f"Groep {group_id} heeft ongeldige rollen ({'; '.join(details)})."
            )

        variants.sort(key=lambda variant: variant.variant_id)
        groups.append(
            JokeGroup(
                group_id=group_id,
                title=titles_by_group[group_id],
                variants=tuple(variants),
            )
        )

    groups.sort(key=lambda group: group.group_id)
    return tuple(groups)
