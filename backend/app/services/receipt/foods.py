import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def _normalize(text: str) -> str:
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9% ]+", " ", text.lower()).strip()


@lru_cache(maxsize=1)
def _non_food_patterns() -> list[re.Pattern]:
    path = DATA_DIR / "non_food_es.json"
    if not path.exists():
        return []
    keywords = json.loads(path.read_text(encoding="utf-8")).get("keywords", [])
    # parole/frasi intere: "gel" dentro "gelatina" non deve far scartare la gelatina
    return [re.compile(rf"(?<![a-z0-9]){re.escape(_normalize(k))}(?![a-z0-9])") for k in keywords if _normalize(k)]


def is_non_food(nome: str) -> bool:
    """True se il nome della riga contiene una parola/frase della lista dei prodotti non
    alimentari (abbigliamento, igiene, pulizia, casa, animali…)."""
    text = _normalize(nome)
    return any(pattern.search(text) for pattern in _non_food_patterns())


@lru_cache(maxsize=1)
def load_fresh_products() -> list[dict]:
    """Voci del catalogo generico dei freschi, nello stesso formato di quello dei
    supermercati (brand/name) più `fresco` e `generico`, così matching e flag `fresco`
    li trattano come le altre voci."""
    path = DATA_DIR / "fresh_products_es.json"
    if not path.exists():
        return []
    categories = json.loads(path.read_text(encoding="utf-8")).get("categorie", {})
    return [
        {"brand": "", "name": name, "fresco": True, "generico": True, "categoria": category}
        for category, names in categories.items()
        for name in names
    ]
