from app.services.receipt.matching import is_reliable, match_catalog, normalize

PRODUCTS = [
    {"brand": "Hacendado", "name": "Leche entera"},
    {"brand": "Hacendado", "name": "Leche semidesnatada"},
    {"brand": "Danone", "name": "Yogur natural"},
    {"brand": "Hida", "name": "Tomate frito"},
]


def test_match_esatto():
    best = match_catalog("LECHE ENTERA", products=PRODUCTS)[0]
    assert best.label == "Hacendado Leche entera"
    assert is_reliable(best)


def test_espande_le_abbreviazioni_da_scontrino():
    best = match_catalog("LCHE ENT", products=PRODUCTS)[0]
    assert best.label == "Hacendado Leche entera"


def test_ignora_accenti_e_maiuscole():
    assert normalize("Jamón Cocído") == "jamon cocido"


def test_sotto_soglia_non_e_affidabile():
    best = match_catalog("BICICLETA DA CORSA ROSSA", products=PRODUCTS)[0]
    assert not is_reliable(best)


def test_ritorna_al_massimo_k_candidati_ordinati():
    result = match_catalog("LECHE", k=2, products=PRODUCTS)
    assert len(result) == 2
    assert result[0].score >= result[1].score


def test_nome_vuoto_o_catalogo_vuoto():
    assert match_catalog("   ", products=PRODUCTS) == []
    assert match_catalog("LECHE", products=[]) == []


def test_contenimento_nome_piu_corto_nel_catalogo():
    products = [{"brand": "Hacendado", "name": "Pan tostado classic"}]
    best = match_catalog("PAN TOSTADO", products=products)[0]
    assert is_reliable(best)


def test_contenimento_non_scatta_se_copre_poco_del_nome():
    products = [{"brand": "AdeZ", "name": "Oat, Strawberry and Banana"}]
    assert not is_reliable(match_catalog("BANANA", products=products)[0])
