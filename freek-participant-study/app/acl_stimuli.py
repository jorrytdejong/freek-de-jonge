"""Load and validate the locked 90-item ACL stimulus bank."""

from __future__ import annotations

import csv
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from app.acl_config import CONDITION_CODES, STUDY_VERSION

EXPECTED_ITEM_COUNT = 90
EXPECTED_TOPIC_COUNT = 15
EXPECTED_ITEMS_PER_TOPIC = 6
EXPECTED_ITEMS_PER_CONDITION = 15
REQUIRED_COLUMNS = {
    "study_version",
    "item_id",
    "topic_id",
    "topic",
    "condition_code",
    "pipeline_family",
    "freek_style",
    "text",
    "model",
    "result_sha256",
}
ITEM_ID_PATTERN = re.compile(r"^(T\d{2})-(A1|A2|C1|C2|E1|E2)$")
TOPIC_ID_PATTERN = re.compile(r"^T(0[1-9]|1[0-5])$")
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
DEFAULT_STIMULI_PATH = Path(__file__).resolve().parents[1] / "data" / "acl_jokes.csv"

EXPECTED_CONDITION_METADATA = {
    "A1": ("baseline", "none"),
    "A2": ("baseline", "freek"),
    "C1": ("script_opposition", "none"),
    "C2": ("script_opposition", "freek"),
    "E1": ("validated_gtvh", "none"),
    "E2": ("validated_gtvh", "freek"),
}


class StimulusValidationError(ValueError):
    """Raised when the locked ACL stimulus contract is violated."""


@dataclass(frozen=True)
class JokeItem:
    study_version: str
    item_id: str
    topic_id: str
    topic: str
    condition_code: str
    pipeline_family: str
    freek_style: str
    text: str
    model: str
    result_sha256: str


def load_stimuli(path: Path = DEFAULT_STIMULI_PATH) -> tuple[JokeItem, ...]:
    if not path.is_file():
        raise StimulusValidationError(f"Stimulusbestand niet gevonden: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or ())
        if missing:
            raise StimulusValidationError(
                f"Ontbrekende stimuluskolommen: {', '.join(sorted(missing))}"
            )
        rows = list(reader)
    return validate_stimuli(rows)


def validate_stimuli(rows: list[dict[str, str]]) -> tuple[JokeItem, ...]:
    if len(rows) != EXPECTED_ITEM_COUNT:
        raise StimulusValidationError(
            f"Verwacht {EXPECTED_ITEM_COUNT} stimuli; gevonden {len(rows)}."
        )

    items: list[JokeItem] = []
    seen_ids: set[str] = set()
    topic_labels: dict[str, str] = {}
    for row_number, row in enumerate(rows, start=2):
        values = {
            column: (row.get(column) or "").strip() for column in REQUIRED_COLUMNS
        }
        empty = sorted(column for column, value in values.items() if not value)
        if empty:
            raise StimulusValidationError(
                f"Rij {row_number} heeft lege velden: {', '.join(empty)}."
            )
        item_id = values["item_id"]
        topic_id = values["topic_id"]
        condition = values["condition_code"]
        match = ITEM_ID_PATTERN.fullmatch(item_id)
        if not match or match.group(1) != topic_id or match.group(2) != condition:
            raise StimulusValidationError(
                f"Rij {row_number} heeft een ongeldige item-ID-koppeling."
            )
        if not TOPIC_ID_PATTERN.fullmatch(topic_id):
            raise StimulusValidationError(f"Ongeldig topic_id: {topic_id}.")
        if item_id in seen_ids:
            raise StimulusValidationError(f"Dubbel item_id: {item_id}.")
        seen_ids.add(item_id)
        if values["study_version"] != STUDY_VERSION:
            raise StimulusValidationError(
                f"Rij {row_number} gebruikt niet study_version {STUDY_VERSION}."
            )
        expected_family, expected_style = EXPECTED_CONDITION_METADATA[condition]
        if (
            values["pipeline_family"] != expected_family
            or values["freek_style"] != expected_style
        ):
            raise StimulusValidationError(
                f"Rij {row_number} heeft metadata die niet bij {condition} past."
            )
        if values["model"] != "gpt-5.6-terra":
            raise StimulusValidationError(f"Rij {row_number} gebruikt een ander model.")
        if not HASH_PATTERN.fullmatch(values["result_sha256"]):
            raise StimulusValidationError(f"Rij {row_number} heeft een ongeldige hash.")
        previous_label = topic_labels.setdefault(topic_id, values["topic"])
        if previous_label != values["topic"]:
            raise StimulusValidationError(f"Topic {topic_id} heeft meerdere labels.")
        items.append(JokeItem(**values))

    topic_counts = Counter(item.topic_id for item in items)
    condition_counts = Counter(item.condition_code for item in items)
    if len(topic_counts) != EXPECTED_TOPIC_COUNT or set(topic_counts.values()) != {
        EXPECTED_ITEMS_PER_TOPIC
    }:
        raise StimulusValidationError("De topicverdeling is niet 15 × 6.")
    if condition_counts != Counter(
        {condition: EXPECTED_ITEMS_PER_CONDITION for condition in CONDITION_CODES}
    ):
        raise StimulusValidationError("De zes condities bevatten niet elk 15 items.")
    return tuple(sorted(items, key=lambda item: item.item_id))
