import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from rapidfuzz import fuzz, process

from app.services.ocr.product_catalog import MATCH_SCORE_THRESHOLD, load_catalog_products, product_label
from app.services.receipt.foods import load_fresh_products

ABBREVIATIONS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "receipt_abbreviations.json"


@dataclass
class CatalogMatch:
    label: str
    brand: str
    name: str
    score: float
    fresco: bool | None = None


@lru_cache(maxsize=1)
def _abbreviations() -> dict[str, str]:
    if not ABBREVIATIONS_PATH.exists():
        return {}
    return json.loads(ABBREVIATIONS_PATH.read_text(encoding="utf-8")).get("abbreviations", {})


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def normalize(text: str, expand_abbreviations: bool = False) -> str:
    text = _strip_accents(text).upper()
    abbreviations = _abbreviations() if expand_abbreviations else {}
    tokens = [abbreviations.get(tok, tok) for tok in re.split(r"\s+", text) if tok]
    text = " ".join(tokens)
    text = re.sub(r"[^A-Z0-9% ]+", " ", text.upper())
    return re.sub(r"\s+", " ", text).strip().lower()


def _all_products() -> list[dict]:
    """Catalogo supermercati (prodotti di marca) + lista dei freschi comuni (nomi
    generici: banana, kiwi, pechuga de pollo…) che nel catalogo di marca mancano."""
    return load_catalog_products() + load_fresh_products()


@lru_cache(maxsize=1)
def _normalized_catalog() -> tuple[list[dict], list[str], list[str]]:
    products = _all_products()
    return (
        products,
        [normalize(p.get("name", "")) for p in products],
        [normalize(product_label(p)) for p in products],
    )


# lo scontrino di norma non stampa la marca: il confronto principale è sul solo nome
# del prodotto; quello su "marca nome" vale un po' meno (la marca può comparire, ma un
# match che regge solo grazie a lei è meno affidabile)
_LABEL_SCORE_WEIGHT = 0.95
_MIN_CONTAINMENT_COVERAGE = 0.5
_STOPWORDS = {"de", "del", "la", "el", "los", "las", "al", "en", "con", "sin", "y", "a", "un", "una"}


def match_catalog(
    nome: str,
    k: int = 3,
    products: list[dict] | None = None,
) -> list[CatalogMatch]:
    """Fino a `k` voci del catalogo più simili al nome letto sullo scontrino, dalla più
    alla meno simile. Le abbreviazioni da scontrino vengono espanse prima del confronto.

    Si usa token_sort_ratio (somiglianza dell'intera stringa, insensibile all'ordine
    delle parole) e non WRatio: WRatio include il confronto "parziale", per cui un nome
    breve come "BANANA" o "KIWI" otteneva punteggi alti contro qualunque etichetta lunga
    che lo contenesse ("yogurt avena fragola e banana"), producendo abbinamenti sbagliati
    ma "affidabili". `products` è parametrizzabile per i test.
    Chi chiama decide cosa è "affidabile" (vedi is_reliable)."""
    if products is None:
        products, names, labels = _normalized_catalog()
    else:
        names = [normalize(p.get("name", "")) for p in products]
        labels = [normalize(product_label(p)) for p in products]
    query = normalize(nome, expand_abbreviations=True)
    if not query or not labels:
        return []

    scores: dict[int, float] = {}
    for _, score, index in process.extract(query, names, scorer=fuzz.token_sort_ratio, limit=k * 3):
        scores[index] = float(score)
    for _, score, index in process.extract(query, labels, scorer=fuzz.token_sort_ratio, limit=k * 3):
        scores[index] = max(scores.get(index, 0.0), float(score) * _LABEL_SCORE_WEIGHT)

    # contenimento: tutte le parole dello scontrino sono nel nome del catalogo e ne
    # coprono almeno metà ("PAN TOSTADO" in "Pan tostado classic"). token_sort_ratio
    # penalizza i nomi del catalogo più lunghi, ma qui il match è affidabile; la soglia
    # di copertura evita "BANANA" -> "yogurt avena, fragola e banana".
    query_tokens = set(query.split())
    if len(query_tokens) >= 1 and any(len(t) >= 3 for t in query_tokens):
        for index, name in enumerate(names):
            name_tokens = name.split()
            if name_tokens and query_tokens <= set(name_tokens):
                coverage = len(query_tokens) / len(name_tokens)
                if coverage >= _MIN_CONTAINMENT_COVERAGE:
                    scores[index] = max(scores.get(index, 0.0), 80.0 + 15.0 * coverage)

    # contenimento inverso, solo per le voci generiche (freschi): il nome generico è
    # contenuto nella riga ("KIWI" in "KIWI VERDE CESTA", "UVA BLANCA" in "UVA BLANCA SIN
    # SEM"). Non vale per le voci di marca, dove nomi brevi come "Natural" starebbero
    # dentro qualunque riga. Si ignorano le parole vuote (de, al, sin…).
    query_content = query_tokens - _STOPWORDS
    if query_content:
        for index, product in enumerate(products):
            if not product.get("generico"):
                continue
            name_content = set(names[index].split()) - _STOPWORDS
            if name_content and name_content <= query_content:
                score = min(95.0, 82.0 + 10.0 * len(name_content) / len(query_content))
                scores[index] = max(scores.get(index, 0.0), score)

    # a parità di punteggio prevale la voce generica (lista freschi, curata): la riga
    # dello scontrino non ha la marca, e il flag `fresco` è correggibile dall'utente
    best = sorted(scores.items(), key=lambda item: (item[1], bool(products[item[0]].get("generico"))), reverse=True)[:k]
    return [
        CatalogMatch(
            label=product_label(products[index]),
            brand=products[index].get("brand", ""),
            name=products[index].get("name", ""),
            score=score,
            fresco=products[index].get("fresco"),
        )
        for index, score in best
    ]


def is_reliable(match: CatalogMatch) -> bool:
    return match.score >= MATCH_SCORE_THRESHOLD
