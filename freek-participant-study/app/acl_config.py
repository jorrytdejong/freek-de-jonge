"""Locked identifiers and questionnaire text for the ACL experiment."""

APP_VERSION = "1.5.0"
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
)

RATING_QUESTIONS = {
    "funniness": "Hoe grappig is deze grap?",
    "freek_similarity": ("In hoeverre lijkt deze grap op de stijl van Freek de Jonge?"),
    "coherence": "Is deze grap logisch als grap?",
}

RATING_ENDPOINTS = {
    "funniness": ("Helemaal niet grappig", "Heel grappig"),
    "freek_similarity": ("Helemaal niet", "Heel sterk"),
    "coherence": ("Onsamenhangend", "Zeer samenhangend"),
}

OPEN_COMMENT_QUESTION = "Wat maakt dat deze grap wel of niet werkt? (optioneel)"
