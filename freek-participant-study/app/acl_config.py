"""Locked identifiers and questionnaire text for the ACL experiment."""

APP_VERSION = "1.4.0"
STUDY_VERSION = "acl-1"
ITEMS_PER_PARTICIPANT = 20
MINIMUM_PARTICIPANTS = 25
TARGET_PARTICIPANTS = 40
MAXIMUM_PARTICIPANTS = 50
NETWORK_PARTICIPANTS = 25
PROLIFIC_PARTICIPANTS = 25
CONDITION_CODES = ("A1", "A2", "C1", "C2", "E1", "E2")
RATING_DIMENSIONS = (
    "funniness",
    "freek_similarity",
    "coherence",
    "originality",
)

RATING_QUESTIONS = {
    "funniness": "Hoe grappig vind je deze grap?",
    "freek_similarity": ("In hoeverre lijkt deze grap op de stijl van Freek de Jonge?"),
    "coherence": "In hoeverre is deze grap coherent en begrijpelijk als grap?",
    "originality": "Hoe origineel vind je deze grap?",
}

RATING_ENDPOINTS = {
    "funniness": ("Helemaal niet grappig", "Heel grappig"),
    "freek_similarity": ("Helemaal niet", "Heel erg"),
    "coherence": ("Helemaal niet coherent", "Zeer coherent"),
    "originality": ("Zeer algemeen", "Zeer origineel"),
}
