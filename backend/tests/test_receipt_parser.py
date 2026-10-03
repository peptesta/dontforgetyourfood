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


def test_scarta_testo_fantasma_minuscolo_dal_retro():
    rows = [[("LONCHAS VACA TIERNO", 0), ("43 ultsnuor fislo", 200), ("1,65 A", 300)]]
    result = parse_receipt_photo(ocr(rows))
    assert [(l.nome, l.prezzo) for l in result] == [("LONCHAS VACA TIERNO", 1.65)]


def test_foto_inclinata_prezzo_sfalsato_va_alla_riga_giusta():
    # testo inclinato di ~3°: i prezzi a destra stanno più in basso dei nomi a sinistra,
    # per un offset che senza raddrizzamento li assegnerebbe alla riga successiva
    import math

    slope = math.tan(math.radians(3))
    lines = []
    for r, (name, price) in enumerate([("PAN TOSTADO", "2,25 A"), ("JAMON SERRANO", "2,75 B"), ("SOLOMILLO", "3,95 B")]):
        for text, x0, w in ((name, 0, 400), (price, 1000, 120)):
            y0 = r * 45 + x0 * slope
            y1 = y0 + 30
            lines.append(
                {
                    "text": text,
                    "confidence": 0.95,
                    "box": [[x0, y0], [x0 + w, y0 + w * slope], [x0 + w, y1 + w * slope], [x0, y1]],
                }
            )
    result = parse_receipt_photo(lines)
    assert [(l.nome, l.prezzo) for l in result] == [("PAN TOSTADO", 2.25), ("JAMON SERRANO", 2.75), ("SOLOMILLO", 3.95)]


def test_toglie_codice_articolo_ed_eur():
    result = parse_receipt_photo(ocr([[("ARNES PERRO-0500229", 0), ("6,99 C", 300)]]))
    assert result[0].nome == "ARNES PERRO"


def test_riga_con_nome_ma_senza_prezzo_letto_viene_tenuta():
    rows = [
        [("LECHE ENTERA", 0), ("0,89", 300)],
        [("UVA BLANCA SIN SEM", 0), ("69Z", 300)],
        [("PAN DE MOLDE", 0), ("1,35", 300)],
    ]
    result = parse_receipt_photo(ocr(rows))
    assert [(l.nome, l.prezzo) for l in result] == [("LECHE ENTERA", 0.89), ("UVA BLANCA SIN SEM", None), ("PAN DE MOLDE", 1.35)]


def test_intestazione_senza_prezzo_non_diventa_prodotto():
    rows = [[("LIDL SUPERMERCADOS S.A.U", 0)], [("PAN TOSTADO", 0), ("2,25 A", 300)]]
    assert [l.nome for l in parse_receipt_photo(ocr(rows))] == ["PAN TOSTADO"]


def test_dalle_foto_successive_alla_prima_non_c_e_intestazione():
    rows = [[("UVA BLANCA SIN SEM", 0)], [("PAN TOSTADO", 0), ("2,25 A", 300)]]
    assert [l.nome for l in parse_receipt_photo(ocr(rows), foto=1)] == ["UVA BLANCA SIN SEM", "PAN TOSTADO"]


def test_dopo_il_totale_e_piede_di_pagina():
    rows = [[("PAN TOSTADO", 0), ("2,25 A", 300)], [("TOTAL", 0), ("2,25", 300)], [("NUMERO OPERACION", 0)], [("QUALCOSA STRANO", 0)]]
    assert [l.nome for l in parse_receipt_photo(ocr(rows))] == ["PAN TOSTADO"]


def test_frammento_prezzo_della_riga_tagliata_viene_scartato():
    rows = [[("NUEZ NATURAL", 0), ("2,65", 300), ("2,09 D", 340)]]
    lines = ocr(rows)
    lines[-1]["confidence"] = 0.6
    result = parse_receipt_photo(lines)
    assert [(l.nome, l.prezzo) for l in result] == [("NUEZ NATURAL", 2.65)]
