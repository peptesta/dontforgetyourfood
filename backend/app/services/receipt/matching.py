import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from rapidfuzz import fuzz, process

from app.services.ocr.product_catalog import MATCH_SCORE_THRESHOLD, load_catalog_products, product_label

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


@lru_cache(maxsize=1)
def _normalized_catalog() -> tuple[list[dict], list[str]]:
    products = load_catalog_products()
    return products, [normalize(product_label(p)) for p in products]


def match_catalog(
    nome: str,
    k: int = 3,
    products: list[dict] | None = None,
) -> list[CatalogMatch]:
    """Fino a `k` voci del catalogo più simili al nome letto sullo scontrino, dalla più
    alla meno simile. Le abbreviazioni da scontrino vengono espanse prima del confronto.
    `products` è parametrizzabile per i test; nell'uso reale viene dal catalogo su disco.
    Chi chiama decide cosa è "affidabile" (vedi is_reliable)."""
    if products is None:
        products, labels = _normalized_catalog()
    else:
        labels = [normalize(product_label(p)) for p in products]
    query = normalize(nome, expand_abbreviations=True)
    if not query or not labels:
        return []

    results = process.extract(query, labels, scorer=fuzz.WRatio, limit=k)
    return [
        CatalogMatch(
            label=product_label(products[index]),
            brand=products[index].get("brand", ""),
            name=products[index].get("name", ""),
            score=float(score),
            fresco=products[index].get("fresco"),
        )
        for _, score, index in results
    ]


def is_reliable(match: CatalogMatch) -> bool:
    return match.score >= MATCH_SCORE_THRESHOLD
