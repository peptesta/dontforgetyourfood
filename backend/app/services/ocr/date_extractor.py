import re
from dataclasses import dataclass, field
from datetime import date, timedelta

SPANISH_MONTHS = {
    "ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AGO": 8, "SEP": 9, "SET": 9, "OCT": 10, "NOV": 11, "DIC": 12,
}

EXPIRY_KEYWORDS = [
    "FECHA DE CADUCIDAD",
    "CONSUMIR PREFERENTEMENTE ANTES DE",
    "CONSUMIR PREFERENTEMENTE",
    "CONS. PREF.",
    "CADUCIDAD",
    "CPAD",
    "CAD.",
    "CAD",
    "EXP",
]

# il gruppo finale opzionale scarta un eventuale orario affiancato alla data (es.
# "12/10/2026 14:30"); il separatore è anch'esso opzionale perché a volte l'OCR
# restituisce l'ora incollata senza spazio (es. "12/10/202614:30"), caso in cui il
# solo \b finale non troverebbe un confine dentro la sequenza di cifre.
_TIME_SUFFIX = r"(?:[ T]?\d{1,2}:\d{2}(?::\d{2})?)?"
# separatori con spazi opzionali: l'OCR su stampe puntinate legge "19. 11. 2026"
NUMERIC_DATE_RE = re.compile(
    rf"\b(\d{{1,2}})\s?[/.\-]\s?(\d{{1,2}})\s?[/.\-]\s?(\d{{2,4}}){_TIME_SUFFIX}\b"
)
# solo mese/anno ("11/2026", "11.26"): la scadenza è l'ultimo giorno del mese
MONTH_YEAR_RE = re.compile(r"(?<![\d/.\-])(\d{1,2})\s?[/.\-]\s?(20\d{2})(?![\d/.\-:])")
_MONTHS_PATTERN = "|".join(SPANISH_MONTHS.keys())
TEXTUAL_DATE_RE = re.compile(
    rf"\b(\d{{1,2}})\s*[- ]?\s*({_MONTHS_PATTERN})\.?\s*[- ]?\s*(\d{{2,4}}){_TIME_SUFFIX}\b", re.IGNORECASE
)

MAX_HORIZON_YEARS = 10  # conserve e scatolame arrivano facilmente a 5-8 anni


@dataclass
class DateCandidate:
    value: date
    source_text: str
    near_keyword: bool = False


@dataclass
class DateExtractionResult:
    best: str | None
    alternatives: list[str] = field(default_factory=list)


def _normalize_year(year: int) -> int:
    return 2000 + year if year < 100 else year


def _safe_date(day: int, month: int, year: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _plausible_expiry(d: date, today: date) -> bool:
    return today - timedelta(days=1) <= d <= today + timedelta(days=365 * MAX_HORIZON_YEARS)


def _find_numeric_dates(text: str) -> list[DateCandidate]:
    out = []
    for m in NUMERIC_DATE_RE.finditer(text):
        day, month, year = int(m.group(1)), int(m.group(2)), _normalize_year(int(m.group(3)))
        d = _safe_date(day, month, year)
        if d:
            out.append(DateCandidate(d, m.group(0)))
    return out


def _find_month_year_dates(text: str) -> list[DateCandidate]:
    out = []
    full_spans = [m.span() for m in NUMERIC_DATE_RE.finditer(text)]
    for m in MONTH_YEAR_RE.finditer(text):
        if any(a <= m.start() and m.end() <= b for a, b in full_spans):
            continue  # "11. 2026" dentro "19. 11. 2026" non è una data a sé
        month, year = int(m.group(1)), int(m.group(2))
        if not 1 <= month <= 12:
            continue
        nxt = date(year + (month == 12), month % 12 + 1, 1)
        out.append(DateCandidate(nxt - timedelta(days=1), m.group(0)))
    return out


def _find_textual_dates(text: str) -> list[DateCandidate]:
    out = []
    for m in TEXTUAL_DATE_RE.finditer(text):
        day = int(m.group(1))
        month = SPANISH_MONTHS[m.group(2).upper()]
        year = _normalize_year(int(m.group(3)))
        d = _safe_date(day, month, year)
        if d:
            out.append(DateCandidate(d, m.group(0)))
    return out


def _fallback_dateparser(text: str) -> list[DateCandidate]:
    try:
        from dateparser.search import search_dates
    except ImportError:
        return []
    try:
        results = search_dates(
            text,
            languages=["es"],
            settings={"DATE_ORDER": "DMY", "PREFER_DATES_FROM": "future"},
        )
    except Exception:
        results = None
    if not results:
        return []
    # dateparser interpreta come date anche sequenze di cifre (lotti: "2611193080") e
    # parole qualsiasi (come "oggi"): si tengono solo i match che hanno l'aspetto di una
    # data, cioè un separatore tra cifre o il nome di un mese.
    def looks_like_date(matched: str) -> bool:
        return bool(re.search(r"\d\s?[/.\-]\s?\d", matched)) or bool(
            re.search(_MONTHS_PATTERN, matched, re.IGNORECASE) and re.search(r"\d", matched)
        )

    return [DateCandidate(dt.date(), m) for m, dt in results if looks_like_date(m)]


def _collect_candidates(lines: list[str]) -> tuple[list[DateCandidate], list[DateCandidate]]:
    """Per ogni riga cerca date, distinguendo quelle vicine a una keyword di scadenza
    dalle altre. Esposta separatamente da extract_date_candidates perché
    scripts/debug_ocr.py la richiama per mostrare il dettaglio riga-per-riga della
    decisione, senza duplicare qui la logica di ricerca."""
    keyword_candidates: list[DateCandidate] = []
    other_candidates: list[DateCandidate] = []

    for i, line in enumerate(lines):
        upper = line.upper()
        has_keyword = any(kw in upper for kw in EXPIRY_KEYWORDS)
        window = line if not has_keyword or i + 1 >= len(lines) else f"{line} {lines[i + 1]}"
        found = _find_numeric_dates(window) + _find_textual_dates(window) + _find_month_year_dates(window)
        for c in found:
            c.near_keyword = has_keyword
            (keyword_candidates if has_keyword else other_candidates).append(c)

    return keyword_candidates, other_candidates


def extract_date_candidates(lines: list[str], today: date | None = None) -> DateExtractionResult:
    """lines: testo OCR riga per riga, nell'ordine restituito dal detector."""
    today = today or date.today()

    keyword_candidates, other_candidates = _collect_candidates(lines)

    if not keyword_candidates and not other_candidates:
        other_candidates = _fallback_dateparser("\n".join(lines))

    plausible_keyword = [c for c in keyword_candidates if _plausible_expiry(c.value, today)]
    plausible_other = [c for c in other_candidates if _plausible_expiry(c.value, today)]

    if plausible_keyword:
        pool = plausible_keyword
    elif plausible_other:
        pool = plausible_other
    else:
        pool = keyword_candidates + other_candidates

    if not pool:
        return DateExtractionResult(best=None, alternatives=[])

    # tra i candidati plausibili, la scadenza è la più lontana nel tempo
    # (produzione/lotto tendono a essere oggi o nel passato)
    unique_dates: list[date] = []
    seen: set[date] = set()
    for c in sorted(pool, key=lambda c: c.value, reverse=True):
        if c.value not in seen:
            seen.add(c.value)
            unique_dates.append(c.value)

    return DateExtractionResult(
        best=unique_dates[0].isoformat(),
        alternatives=[d.isoformat() for d in unique_dates[1:]],
    )
