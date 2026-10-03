"""Script una tantum: scarica da Open Food Facts l'elenco di prodotti Lidl/Mercadona/
Alcampo in Spagna e genera backend/app/data/product_catalog_es.json, usato dal fuzzy-matching
in app/services/ocr/product_catalog.py per suggerire un nome prodotto quando la
confidenza OCR sul titolo è bassa (vedi NEXT_SESSION.md e il piano di implementazione).

Fonte dati: Open Food Facts (https://world.openfoodfacts.org), licenza ODbL
(https://opendatacommons.org/licenses/odbl/1-0/) — la ridistribuzione dei dati
richiede attribuzione, riportata nel file generato.

Uso: python scripts/fetch_product_catalog.py
(va rilanciato manualmente per aggiornare il catalogo o aggiungere altre catene)
"""
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = "https://world.openfoodfacts.org/api/v2/search"
# ordinate dalla più piccola alla più grande: se l'API inizia a rate-limitare (già
# successo, risponde 503/401 dopo qualche centinaio di richieste) si vuole aver
# comunque completato le catene più piccole prima di rimanere bloccati su Mercadona.
STORES = ["alcampo", "lidl", "mercadona"]
COUNTRY = "spain"
PAGE_SIZE = 100  # il server ignora valori più alti e limita comunque a 100
REQUEST_DELAY_SECONDS = 1.5  # rispetta il servizio gratuito, evita 429/503
MAX_RETRIES = 8
MAX_BACKOFF_SECONDS = 20.0

USER_AGENT = "Scadenzario/1.0 (product catalog fetch script; uso interno, non commerciale)"

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "app" / "data" / "product_catalog_es.json"


def _fetch_page(store: str, page: int) -> dict:
    url = (
        f"{BASE_URL}?stores_tags_en={store}&countries_tags_en={COUNTRY}"
        f"&fields=product_name,brands&page_size={PAGE_SIZE}&page={page}"
    )
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read())
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            wait = min(REQUEST_DELAY_SECONDS * (2**attempt), MAX_BACKOFF_SECONDS)
            print(f"  tentativo {attempt}/{MAX_RETRIES} fallito ({exc}), riprovo tra {wait:.0f}s")
            time.sleep(wait)
    raise RuntimeError(f"impossibile scaricare {store} pagina {page}") from last_error


def _split_brands(raw_brands: str) -> list[str]:
    if not raw_brands.strip():
        return [""]
    parts = [b.strip() for b in raw_brands.split(",")]
    return [p for p in parts if p] or [""]


def fetch_store(store: str) -> tuple[list[dict], bool]:
    """Ritorna (entries, complete). Se una pagina fallisce dopo tutti i retry, si
    interrompe quella catena ma si ritornano comunque le pagine già scaricate: meglio
    un catalogo parziale (rilanciabile in un secondo momento) che perdere tutto."""
    entries: list[dict] = []
    page = 1
    page_count = 1
    while page <= page_count:
        try:
            data = _fetch_page(store, page)
        except RuntimeError as exc:
            print(f"{store}: interrotto alla pagina {page}/{page_count} ({exc}) — proseguo con quanto scaricato")
            return entries, False

        page_count = data.get("page_count", page)
        products = data.get("products", [])
        print(f"{store}: pagina {page}/{page_count} ({len(products)} prodotti)")

        for product in products:
            name = (product.get("product_name") or "").strip()
            if not name:
                continue
            for brand in _split_brands(product.get("brands") or ""):
                entries.append({"brand": brand, "name": name})

        page += 1
        if page <= page_count:
            time.sleep(REQUEST_DELAY_SECONDS)
    return entries, True


def main() -> None:
    all_entries: list[dict] = []
    complete = True
    for store in STORES:
        store_entries, store_complete = fetch_store(store)
        all_entries.extend(store_entries)
        complete = complete and store_complete

    # dedup preservando l'ordine di inserimento
    seen: set[tuple[str, str]] = set()
    deduped: list[dict] = []
    for entry in all_entries:
        key = (entry["brand"].lower(), entry["name"].lower())
        if key not in seen:
            seen.add(key)
            deduped.append(entry)

    output = {
        "_source": "Open Food Facts (https://world.openfoodfacts.org), ODbL license "
        "(https://opendatacommons.org/licenses/odbl/1-0/)",
        "_stores": STORES,
        "_country": COUNTRY,
        "_complete": complete,
        "products": deduped,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    status = "completo" if complete else "PARZIALE (rilanciare lo script più tardi per completarlo)"
    print(f"Scritte {len(deduped)} voci in {OUTPUT_PATH} — catalogo {status}")


if __name__ == "__main__":
    main()
