import re

ISO_DATE = re.compile(r"\b\d{4}-\d{2}(?:-\d{2})?\b")
MONTH_DATE = re.compile(
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|"
    r"Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+(?:\d{1,2},?\s+)?\d{4}\b",
    re.IGNORECASE,
)
ORDINAL_REFERENCE = re.compile(r"\b(?:section|step|stage|part|item|figure|table|chapter|state)\s+\d+\b", re.IGNORECASE)
NUMBER = re.compile(r"(?<![\w.])([+\-−]?)(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(\s?%)?(?![\w])")
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
YEAR_RANGE = (1900, 2100)
MATCH_SLACK = 1e-9


def mask(text: str, pattern: re.Pattern) -> str:
    return pattern.sub(lambda match: " " * len(match.group(0)), text)


def source_numbers(value) -> list[float]:
    if isinstance(value, bool) or value is None:
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, dict):
        return [number for item in value.values() for number in source_numbers(item)]
    if isinstance(value, (list, tuple)):
        return [number for item in value for number in source_numbers(item)]
    return []


def source_years(value) -> set[int]:
    if isinstance(value, str):
        return {int(year) for year in re.findall(r"\b(\d{4})-\d{2}", value)}
    if isinstance(value, dict):
        return set().union(*[source_years(item) for item in value.values()]) if value else set()
    if isinstance(value, (list, tuple)):
        return set().union(*[source_years(item) for item in value]) if value else set()
    return set()


def sentence_at(text: str, position: int) -> str:
    start = 0
    for boundary in SENTENCE_BOUNDARY.finditer(text):
        if boundary.start() >= position:
            return text[start:boundary.start()].strip()
        start = boundary.end()
    return text[start:].strip()


def candidates(value: float, decimals: int, is_percent: bool) -> list[tuple[float, int]]:
    if is_percent:
        return [(value / 100.0, decimals + 2), (value, decimals)]
    return [(value, decimals)]


def is_verified(value: float, decimals: int, is_percent: bool, numbers: list[float]) -> bool:
    for candidate, precision in candidates(abs(value), decimals, is_percent):
        tolerance = 0.5 * 10 ** (-precision) + MATCH_SLACK
        if any(abs(abs(number) - candidate) <= tolerance for number in numbers):
            return True
    return False


def extract_numbers(text: str, years: set[int]) -> list[dict]:
    cleaned = mask(mask(mask(text, ISO_DATE), MONTH_DATE), ORDINAL_REFERENCE)
    found = []
    for match in NUMBER.finditer(cleaned):
        sign, integer, fraction, percent = match.groups()
        has_separator = "," in integer
        value = float(integer.replace(",", "") + (fraction or ""))
        if sign in ("-", "−"):
            value = -value
        is_percent = bool(percent)
        if not fraction and not is_percent and not has_separator and not sign:
            if YEAR_RANGE[0] <= value <= YEAR_RANGE[1] and int(value) in years:
                continue
        found.append({
            "text": match.group(0).strip(),
            "value": value,
            "decimals": len(fraction) - 1 if fraction else 0,
            "is_percent": is_percent,
            "position": match.start(),
        })
    return found


def verify_section(text: str, source) -> dict:
    numbers = source_numbers(source)
    years = source_years(source)
    unverified = []
    extracted = extract_numbers(text, years)
    for item in extracted:
        if not is_verified(item["value"], item["decimals"], item["is_percent"], numbers):
            unverified.append({"number": item["text"], "sentence": sentence_at(text, item["position"])})
    return {"total": len(extracted), "verified": len(extracted) - len(unverified), "unverified": unverified}


def verify_numbers(text_sections: dict, source_json: dict) -> dict:
    sections = {
        section_id: verify_section(text, source_json.get(section_id, source_json))
        for section_id, text in text_sections.items()
    }
    total = sum(item["total"] for item in sections.values())
    verified = sum(item["verified"] for item in sections.values())
    return {
        "sections": sections,
        "numbers_total": total,
        "numbers_verified": verified,
        "flagged": verified < total,
    }
