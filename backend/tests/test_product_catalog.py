from app.services.ocr.product_catalog import suggest_product_name

CATALOG = [
    "Hacendado Guacamole",
    "Hacendado Crema de cacahuetes 100%",
    "MERCADONA Corn flakes 0% azucares anadidos",
    "elPozo JAMON COCIDO",
    "Alesto Anacardo natural",
]


def test_suggerisce_match_con_piccolo_errore_di_battitura():
    result = suggest_product_name("Hacendado Guacamol", confidence=0.4, entries=CATALOG)
    assert result == "Hacendado Guacamole"


def test_nessun_suggerimento_se_confidenza_gia_alta():
    # non viene nemmeno interrogato il catalogo se l'OCR era già sicuro
    result = suggest_product_name("Testo qualsiasi", confidence=0.9, entries=CATALOG)
    assert result is None


def test_nessun_suggerimento_sotto_soglia_di_similarita():
    result = suggest_product_name("Bicicletta da corsa rossa", confidence=0.3, entries=CATALOG)
    assert result is None


def test_nessun_suggerimento_con_candidato_vuoto():
    result = suggest_product_name("   ", confidence=0.2, entries=CATALOG)
    assert result is None


def test_nessun_suggerimento_con_catalogo_vuoto():
    result = suggest_product_name("Hacendado Guacamole", confidence=0.2, entries=[])
    assert result is None


def test_confidenza_none_viene_trattata_come_bassa():
    result = suggest_product_name("elPozo JAMON COCIDO", confidence=None, entries=CATALOG)
    assert result == "elPozo JAMON COCIDO"


def test_suggerimento_dal_catalogo_e_nel_formato_titolo_con_marca(monkeypatch):
    from app.services.ocr import product_catalog

    monkeypatch.setattr(
        product_catalog,
        "load_catalog_products",
        lambda: [{"brand": "Hacendado", "name": "Guacamole"}, {"brand": "", "name": "Pan tostado"}],
    )
    assert suggest_product_name("Hacendado Guacamol", confidence=0.4) == "Guacamole (Hacendado)"
    assert suggest_product_name("Pan tostado", confidence=0.4) == "Pan tostado"
