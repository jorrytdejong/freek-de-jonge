from __future__ import annotations


CATEGORY_INVENTORY: dict[str, dict[str, str]] = {
    "Domheid": {
        "description": "Laughing at ignorance, foolish action, or feigned stupidity.",
        "setup_script": "competence, status, or assumed intelligence",
        "opposing_script": "ignorance, foolishness, or deliberately performed stupidity",
        "trigger": "a respected person reveals a basic misunderstanding",
    },
    "Zelfspot": {
        "description": "The speaker makes fun of himself, turning self-lowering into strength.",
        "setup_script": "the speaker as morally or intellectually authoritative",
        "opposing_script": "the speaker as weak, vain, afraid, or ridiculous",
        "trigger": "the speaker undercuts his own authority",
    },
    "Primitieve humor": {
        "description": "Taboo, bodily, naughty, or slapstick humor that breaks etiquette without real harm.",
        "setup_script": "civilized manners and social etiquette",
        "opposing_script": "basic bodily instinct, childish taboo, or harmless physical chaos",
        "trigger": "a polite situation is pulled down to the body or slapstick",
    },
    "Zwarte humor": {
        "description": "Heavy subjects such as death, war, disease, or fear are made bearable through humor.",
        "setup_script": "tragic seriousness, fear, or powerlessness",
        "opposing_script": "mundane practicality or administrative calm",
        "trigger": "a grave subject is treated as an everyday inconvenience",
    },
    "Ironie": {
        "description": "Saying the opposite of what is meant; a playful or intellectual reversal of meaning.",
        "setup_script": "stated belief, public sincerity, or official seriousness",
        "opposing_script": "implied disbelief, private contradiction, or hollow performance",
        "trigger": "a phrase makes the stated belief sound false",
    },
    "Leedvermaak": {
        "description": "Enjoyment of another person's misfortune, clumsiness, or embarrassment.",
        "setup_script": "someone else's control, dignity, or smooth performance",
        "opposing_script": "collapse, clumsiness, or misfortune that spares the observer",
        "trigger": "dignity slips while the observer remains safe",
    },
    "Taalhumor": {
        "description": "Wordplay, puns, ambiguity, grammar, and shifting definitions.",
        "setup_script": "literal meaning",
        "opposing_script": "social, idiomatic, or unintended meaning",
        "trigger": "an ambiguous word or idiom",
    },
    "Overdrijving": {
        "description": "Reality or logic is stretched to absurd scale to reveal a feature of the situation.",
        "setup_script": "ordinary scale of a social situation",
        "opposing_script": "absurdly inflated consequence",
        "trigger": "a small fact is treated as historically enormous",
    },
    "Understatement": {
        "description": "An intense situation is downplayed through cool, minimal, or emotionally absent reaction.",
        "setup_script": "crisis, scandal, or emotional intensity",
        "opposing_script": "calm minimization",
        "trigger": "a severe event is described as a small inconvenience",
    },
    "De slimme observatie": {
        "description": "Observational comedy that questions everyday norms and notices ignored oddities.",
        "setup_script": "an everyday habit seems normal",
        "opposing_script": "the habit is exposed as strange, artificial, or contradictory",
        "trigger": "a familiar detail is reframed as absurd",
    },
    "De plotselinge ommezwaai": {
        "description": "An expectation is built and then sharply violated, often through a broken pattern.",
        "setup_script": "a predictable pattern or expectation",
        "opposing_script": "a sudden violation of that pattern",
        "trigger": "the final phrase breaks the expected continuation",
    },
    "De verkeerde opmerking": {
        "description": "Breaking social politeness by saying something rude, shocking, or unacceptable.",
        "setup_script": "social politeness",
        "opposing_script": "taboo or blunt truth",
        "trigger": "a polite sentence suddenly says the quiet part aloud",
    },
    "Cirkelhumor": {
        "description": "Paradox, circular logic, and self-reference that asserts by denying or denying by asserting.",
        "setup_script": "linear explanation or stable reference",
        "opposing_script": "self-reference, circularity, or paradox",
        "trigger": "the statement loops back on itself",
    },
    "Antihumor": {
        "description": "Intentionally bad jokes, missing punchlines, non sequiturs, or subverted joke form.",
        "setup_script": "a normal joke structure promises a punchline",
        "opposing_script": "the punchline is absent, flat, or logically unrelated",
        "trigger": "the expected comic payoff is deliberately withheld",
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


def category_defaults(category: str | None) -> dict[str, str]:
    """Return semantic defaults for a humor category.

    Args:
        category: Category name, supported alias, or ``None``.

    Returns:
        Category description, scripts, and trigger defaults.
    """
    normalized = normalize_category(category)
    return CATEGORY_INVENTORY.get(
        normalized,
        {
            "description": "A general humor category.",
            "setup_script": "ordinary expectation",
            "opposing_script": "surprising incompatible interpretation",
            "trigger": "a phrase that supports both readings",
        },
    )
