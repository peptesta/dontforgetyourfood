from app.services.receipt.parser import parse_receipt_photo


def ocr(rows: list[list[tuple[str, float]]]) -> list[dict]:
    """Costruisce righe OCR finte: ogni riga è una lista di (testo, x0) sulla stessa y."""
    lines = []
    for r, row in enumerate(rows):
        for text, x0 in row:
            y0 = r * 40
            lines.append(
                {
                    "text": text,
                    "confidence": 0.95,
                    "box": [[x0, y0], [x0 + 100, y0], [x0 + 100, y0 + 30], [x0, y0 + 30]],
                }
            )
    return lines


def test_riga_con_nome_e_prezzo():
    result = parse_receipt_photo(ocr([[("LECHE ENTERA", 0), ("0,89", 300)]]))
    assert [(l.nome, l.prezzo) for l in result] == [("LECHE ENTERA", 0.89)]


def test_toglie_quantita_iniziale():
    result = parse_receipt_photo(ocr([[("2 YOGUR NATURAL", 0), ("1,20", 300)]]))
    assert result[0].nome == "YOGUR NATURAL"


def test_scarta_totali_iva_pagamento_e_intestazione():
    rows = [
        [("MERCADONA S.A.", 0)],
        [("FACTURA SIMPLIFICADA", 0)],
        [("PAN DE MOLDE", 0), ("1,35", 300)],
        [("TOTAL (€)", 0), ("1,35", 300)],
        [("TARJETA BANCARIA", 0), ("1,35", 300)],
        [("IVA 10%", 0), ("0,12", 300)],
    ]
    result = parse_receipt_photo(ocr(rows))
    assert [l.nome for l in result] == ["PAN DE MOLDE"]


def test_scarta_righe_quantita_e_barcode():
    rows = [
        [("ARROZ REDONDO", 0), ("1,10", 300)],
        [("2 x 1,10", 0), ("2,20", 300)],
        [("8410000123456", 0)],
    ]
    result = parse_receipt_photo(ocr(rows))
    assert [l.nome for l in result] == ["ARROZ REDONDO"]


def test_prodotto_a_peso_nome_e_prezzo_su_righe_diverse():
    rows = [
        [("PLATANO", 0)],
        [("0,350 kg 3,99 €/kg", 0), ("1,40", 300)],
    ]
    result = parse_receipt_photo(ocr(rows))
    assert [(l.nome, l.prezzo) for l in result] == [("PLATANO", 1.40)]


def test_scarta_sconti_negativi():
    rows = [[("QUESO FRESCO", 0), ("2,00", 300)], [("DTO QUESO", 0), ("-0,50", 300)]]
    result = parse_receipt_photo(ocr(rows))
    assert [l.nome for l in result] == ["QUESO FRESCO"]


def test_prezzo_con_lettera_iva_finale():
    result = parse_receipt_photo(ocr([[("Leche entera", 0), ("1,09 B", 300)]]))
    assert (result[0].nome, result[0].prezzo) == ("LECHE ENTERA", 1.09)


def test_foto_di_soli_nomi_senza_prezzi():
    result = parse_receipt_photo(ocr([[("LECHE ENTERA", 0)], [("PAN DE MOLDE", 0)]]))
    assert [(l.nome, l.prezzo) for l in result] == [("LECHE ENTERA", None), ("PAN DE MOLDE", None)]
