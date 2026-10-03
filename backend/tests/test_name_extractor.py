from app.services.ocr.name_extractor import extract_product_name, extract_product_name_from_title_photo


def test_sceglie_la_riga_piu_prominente_come_nome():
    lines = [
        {"text": "8410297123456", "confidence": 0.99, "box": [[10, 10], [100, 10], [100, 30], [10, 30]]},
        {"text": "Leche Entera", "confidence": 0.95, "box": [[10, 50], [300, 50], [300, 110], [10, 110]]},
        {"text": "CAD 12/10/26", "confidence": 0.9, "box": [[10, 150], [150, 150], [150, 170], [10, 170]]},
        {"text": "1L", "confidence": 0.8, "box": [[10, 120], [40, 120], [40, 140], [10, 140]]},
    ]
    result = extract_product_name(lines)
    assert result["name"] == "Leche Entera"
    assert "Leche Entera" in result["raw_text"]
    assert "8410297123456" in result["raw_text"]  # raw_text conserva tutto per la Review


def test_unisce_parole_sulla_stessa_riga_nellordine_corretto():
    # Box reali catturati da un'inferenza PaddleOCR: "Entera" ha y0=35, "Leche" ha y0=36
    # (differenza di 1px dovuta al detector) pur essendo "Leche" a sinistra di "Entera".
    # Un ordinamento ingenuo per solo y0 inverte l'ordine di lettura in "Entera Leche".
    lines = [
        {"text": "Leche", "confidence": 0.9997, "box": [[21, 36], [175, 36], [175, 72], [21, 72]]},
        {"text": "Entera", "confidence": 0.99995, "box": [[156, 35], [314, 39], [313, 75], [156, 72]]},
        {"text": "CAD: 12/10/2026", "confidence": 0.999, "box": [[19, 121], [226, 121], [226, 149], [19, 149]]},
        {"text": "8410297123456", "confidence": 0.999, "box": [[19, 162], [218, 162], [218, 191], [19, 191]]},
    ]
    result = extract_product_name(lines)
    assert result["name"] == "Leche Entera"


def test_unisce_righe_impilate_verticalmente():
    lines = [
        {"text": "Barilla", "confidence": 0.99, "box": [[20, 30], [200, 30], [200, 70], [20, 70]]},
        {"text": "Pasta Integrale", "confidence": 0.99, "box": [[20, 75], [280, 75], [280, 115], [20, 115]]},
        {"text": "CAD 12/10/26", "confidence": 0.98, "box": [[20, 160], [180, 160], [180, 185], [20, 185]]},
    ]
    result = extract_product_name(lines)
    assert result["name"] == "Barilla Pasta Integrale"


def test_lista_vuota():
    result = extract_product_name([])
    assert result == {"name": None, "raw_text": ""}


def test_solo_rumore_nessun_nome_valido():
    lines = [
        {"text": "1L", "confidence": 0.8, "box": [[0, 0], [10, 0], [10, 10], [0, 10]]},
        {"text": "12/10/26", "confidence": 0.8, "box": [[0, 20], [50, 20], [50, 30], [0, 30]]},
    ]
    result = extract_product_name(lines)
    assert result["name"] is None


def test_foto_titolo_riga_singola():
    lines = [
        {"text": "Leche Entera", "confidence": 0.95, "box": [[10, 50], [300, 50], [300, 110], [10, 110]]},
    ]
    result = extract_product_name_from_title_photo(lines)
    assert result["name"] == "Leche Entera"


def test_foto_titolo_righe_multiple_impilate_vengono_concatenate():
    lines = [
        {"text": "Barilla", "confidence": 0.99, "box": [[20, 30], [200, 30], [200, 70], [20, 70]]},
        {"text": "Pasta Integrale", "confidence": 0.99, "box": [[20, 75], [280, 75], [280, 115], [20, 115]]},
    ]
    result = extract_product_name_from_title_photo(lines)
    assert result["name"] == "Barilla Pasta Integrale"


def test_foto_titolo_filtra_frammento_codice_residuo_in_frame():
    lines = [
        {"text": "Leche Entera", "confidence": 0.95, "box": [[10, 50], [300, 50], [300, 110], [10, 110]]},
        {"text": "8410297123456", "confidence": 0.99, "box": [[10, 120], [200, 120], [200, 140], [10, 140]]},
    ]
    result = extract_product_name_from_title_photo(lines)
    assert result["name"] == "Leche Entera"
    assert "8410297123456" in result["raw_text"]


def test_foto_titolo_lista_vuota():
    result = extract_product_name_from_title_photo([])
    assert result == {"name": None, "raw_text": ""}


def test_foto_titolo_solo_rumore():
    lines = [
        {"text": "12/10/26", "confidence": 0.8, "box": [[0, 20], [50, 20], [50, 30], [0, 30]]},
    ]
    result = extract_product_name_from_title_photo(lines)
    assert result["name"] is None
