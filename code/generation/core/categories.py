from __future__ import annotations


CATEGORY_INVENTORY: dict[str, dict[str, str]] = {
    "Domheid": {
        "description": "Laughing at ignorance, foolish action, or feigned stupidity.",
    },
    "Zelfspot": {
        "description": "The speaker makes fun of himself, turning self-lowering into strength.",
    },
    "Primitieve humor": {
        "description": "Taboo, bodily, naughty, or slapstick humor that breaks etiquette without real harm.",
    },
    "Zwarte humor": {
        "description": "Heavy subjects such as death, war, disease, or fear are made bearable through humor.",
    },
    "Ironie": {
        "description": "Saying the opposite of what is meant; a playful or intellectual reversal of meaning.",
    },
    "Leedvermaak": {
        "description": "Enjoyment of another person's misfortune, clumsiness, or embarrassment.",
    },
    "Taalhumor": {
        "description": "Wordplay, puns, ambiguity, grammar, and shifting definitions.",
    },
    "Overdrijving": {
        "description": "Reality or logic is stretched to absurd scale to reveal a feature of the situation.",
    },
    "Understatement": {
        "description": "An intense situation is downplayed through cool, minimal, or emotionally absent reaction.",
    },
    "De slimme observatie": {
        "description": "Observational comedy that questions everyday norms and notices ignored oddities.",
    },
    "De plotselinge ommezwaai": {
        "description": "An expectation is built and then sharply violated, often through a broken pattern.",
    },
    "De verkeerde opmerking": {
        "description": "Breaking social politeness by saying something rude, shocking, or unacceptable.",
    },
    "Cirkelhumor": {
        "description": "Paradox, circular logic, and self-reference that asserts by denying or denying by asserting.",
    },
    "Antihumor": {
        "description": "Intentionally bad jokes, missing punchlines, non sequiturs, or subverted joke form.",
    },
}


DEFAULT_CATEGORY = "Ironie"
CATEGORY_ALIASES: dict[str, str] = {
    "stupidity": "Domheid",
    "self-mockery": "Zelfspot",
    "self mockery": "Zelfspot",
    "primitive humor": "Primitieve humor",
    "black humor": "Zwarte humor",
    "dark humor": "Zwarte humor",
    "irony": "Ironie",
    "schadenfreude": "Leedvermaak",
    "language humor": "Taalhumor",
    "exaggeration": "Overdrijving",
    "understatement": "Understatement",
    "clever observation": "De slimme observatie",
    "observational humor": "De slimme observatie",
    "sudden twist": "De plotselinge ommezwaai",
    "inappropriate remark": "De verkeerde opmerking",
    "circular humor": "Cirkelhumor",
    "anti-humor": "Antihumor",
    "antihumor": "Antihumor",
}


def normalize_category(category: str | None) -> str:
    """Return the canonical category name for a label or alias.

    Args:
        category: Category name, supported alias, or ``None``.

    Returns:
        The canonical category name, or the stripped unknown label.
    """
    if not category:
        return DEFAULT_CATEGORY
    cleaned = category.strip().lower()
    for known_category in CATEGORY_INVENTORY:
        if known_category.lower() == cleaned:
            return known_category
    if cleaned in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[cleaned]
    return category.strip()


def category_guidance(category: str | None) -> dict[str, str]:
    """Return descriptive guidance for a humor category.

    Args:
        category: Category name, supported alias, or ``None``.

    Returns:
        Canonical category name and its general description.
    """
    normalized = normalize_category(category)
    details = CATEGORY_INVENTORY.get(normalized, {"description": "A general humor category."})
    return {"category": normalized, "description": details["description"]}


def category_defaults(category: str | None) -> dict[str, str]:
    """Return the legacy prompt fields used by the category pipeline.

    The paper's A/C/E pipelines do not use category conditioning, but the
    shared prompt module imports this compatibility helper at module load
    time. Keeping the fields here makes the extracted package importable
    without retaining the unrelated category-pipeline implementation.
    """
    guidance = category_guidance(category)
    return {
        "category": guidance["category"],
        "description": guidance["description"],
        "setup_script": "an ordinary, topic-compatible interpretation",
        "opposing_script": "a recognizable but conflicting interpretation",
        "trigger": "a late wording or situation shift",
    }
