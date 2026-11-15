import re


SCOPE_DECLINE = (
    "I can help with construction operations, RFIs, project coordination, and related workflows. "
    "Please ask a construction-related question."
)

# shortcut: conservative English patterns catch obvious unrelated requests, not every topic or paraphrase.
# Expand using reviewed examples if broader domain classification becomes necessary.
COOKING_REQUEST = re.compile(
    r"\b(?:cook|grill|fry|bake)\b.{0,60}\b(?:steak|chicken|pasta|cake|cookies|salmon|eggs)\b"
    r"|\b(?:steak|chicken|pasta|cake|cookies|salmon|eggs)\s+recipe\b"
    r"|\brecipe\s+for\s+(?:(?:a|an|the)\s+)?(?:steak|chicken|pasta|cake|cookies|salmon|eggs)\b",
    re.IGNORECASE | re.DOTALL,
)
UNRELATED_REQUEST = re.compile(
    r"\b(?:tell|write|give)\b.{0,30}\b(?:joke|love\s+poem)\b"
    r"|\bcapital\s+of\b"
    r"|\brecommend\b.{0,30}\bmovie\b"
    r"|\bwho\s+won\b.{0,50}\b(?:football|basketball|baseball|soccer|super\s+bowl)\b",
    re.IGNORECASE | re.DOTALL,
)
CONSTRUCTION_CONTEXT = re.compile(
    r"\b(?:construction|rfis?|submittals?|contractors?|subcontractors?|jobsite|toolbox|"
    r"concrete|framing|hvac|mep|electrical|plumbing|specifications?)\b",
    re.IGNORECASE,
)


def is_clearly_unrelated(message: str) -> bool:
    if COOKING_REQUEST.search(message):
        return True
    return bool(UNRELATED_REQUEST.search(message) and not CONSTRUCTION_CONTEXT.search(message))
