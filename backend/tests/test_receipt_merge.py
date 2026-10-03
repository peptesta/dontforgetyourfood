from app.services.receipt.merge import merge_photos
from app.services.receipt.parser import ReceiptLine


def L(nome: str, prezzo: float | None = 1.0) -> ReceiptLine:
    return ReceiptLine(nome=nome, prezzo=prezzo, confidence=0.9)


def names(result) -> list[str]:
    return [l.nome for l in result.lines]


def test_sovrapposizione_di_due_righe():
    a = [L("LECHE", 0.89), L("PAN", 1.35), L("ARROZ", 1.10)]
    b = [L("PAN", 1.35), L("ARROZ", 1.10), L("ATUN", 2.40)]
    result = merge_photos([a, b])
    assert names(result) == ["LECHE", "PAN", "ARROZ", "ATUN"]
    assert result.giunture_senza_sovrapposizione == []


def test_sovrapposizione_di_tre_foto():
    a = [L("A", 1.0), L("B", 2.0)]
    b = [L("B", 2.0), L("C", 3.0), L("D", 4.0)]
    c = [L("C", 3.0), L("D", 4.0), L("E", 5.0)]
    assert names(merge_photos([a, b, c])) == ["A", "B", "C", "D", "E"]


def test_nessuna_sovrapposizione_segnala_la_giuntura():
    a = [L("LECHE", 0.89), L("PAN", 1.35)]
    b = [L("ATUN", 2.40), L("ARROZ", 1.10)]
    result = merge_photos([a, b])
    assert names(result) == ["LECHE", "PAN", "ATUN", "ARROZ"]
    assert result.giunture_senza_sovrapposizione == [0]


def test_tollera_errore_ocr_sul_nome_nella_sovrapposizione():
    a = [L("LECHE ENTERA", 0.89), L("PAN DE MOLDE", 1.35)]
    b = [L("PAN DE MOLDF", 1.35), L("ATUN", 2.40)]
    assert names(merge_photos([a, b])) == ["LECHE ENTERA", "PAN DE MOLDE", "ATUN"]


def test_stesso_nome_con_prezzo_diverso_non_e_sovrapposizione():
    a = [L("LECHE", 0.89), L("YOGUR", 1.20)]
    b = [L("YOGUR", 0.99), L("ATUN", 2.40)]
    result = merge_photos([a, b])
    assert names(result) == ["LECHE", "YOGUR", "YOGUR", "ATUN"]
    assert result.giunture_senza_sovrapposizione == [0]


def test_doppione_vicino_nella_stessa_foto_viene_segnalato():
    a = [L("LECHE", 0.89), L("LECHE", 0.89), L("PAN", 1.35)]
    result = merge_photos([a])
    assert names(result) == ["LECHE", "PAN"]
    assert result.lines[0].possibile_doppione is True
    assert result.lines[1].possibile_doppione is False


def test_foto_contenuta_interamente_nella_precedente():
    a = [L("A", 1.0), L("B", 2.0), L("C", 3.0)]
    b = [L("B", 2.0), L("C", 3.0)]
    assert names(merge_photos([a, b])) == ["A", "B", "C"]


def test_foto_vuota_non_rompe_il_merge():
    a = [L("A", 1.0)]
    assert names(merge_photos([a, []])) == ["A"]


def test_registra_la_foto_di_origine():
    result = merge_photos([[L("A", 1.0)], [L("B", 2.0)]])
    assert [l.foto for l in result.lines] == [0, 1]
