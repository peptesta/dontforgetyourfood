from datetime import date

from app.services.ocr.date_extractor import extract_date_candidates

TODAY = date(2026, 9, 22)


def test_keyword_seguito_da_data_su_riga_successiva():
    lines = ["Leche Entera", "CONSUMIR PREFERENTEMENTE ANTES DE", "25/12/26"]
    result = extract_date_candidates(lines, today=TODAY)
    assert result.best == "2026-12-25"


def test_keyword_e_data_sulla_stessa_riga():
    lines = ["Yogur Natural", "CAD: 03/10/2026"]
    result = extract_date_candidates(lines, today=TODAY)
    assert result.best == "2026-10-03"


def test_mese_abbreviato_spagnolo():
    lines = ["CAD 12 OCT 26"]
    result = extract_date_candidates(lines, today=TODAY)
    assert result.best == "2026-10-12"


def test_scarta_data_produzione_passata_a_favore_di_scadenza_futura():
    lines = ["FAB: 01/09/26", "CAD: 15/12/26"]
    result = extract_date_candidates(lines, today=TODAY)
    assert result.best == "2026-12-15"


def test_ambiguita_senza_keyword_restituisce_alternative():
    lines = ["10/11/26", "20/11/26"]
    result = extract_date_candidates(lines, today=TODAY)
    assert result.best == "2026-11-20"
    assert "2026-11-10" in result.alternatives


def test_nessuna_data_trovata():
    lines = ["Aceite de Oliva Virgen Extra"]
    result = extract_date_candidates(lines, today=TODAY)
    assert result.best is None
    assert result.alternatives == []


def test_anno_a_due_cifre_normalizzato_al_2000():
    lines = ["CAD 01/01/27"]
    result = extract_date_candidates(lines, today=TODAY)
    assert result.best == "2027-01-01"


def test_non_esplode_su_testo_senza_senso():
    lines = ["###??!!", "", "   "]
    result = extract_date_candidates(lines, today=TODAY)
    assert result.best is None


def test_data_con_orario_separato_da_spazio():
    lines = ["CAD: 12/10/2026 14:30"]
    result = extract_date_candidates(lines, today=TODAY)
    assert result.best == "2026-10-12"


def test_data_con_orario_e_secondi():
    lines = ["CAD: 12/10/2026 14:30:00"]
    result = extract_date_candidates(lines, today=TODAY)
    assert result.best == "2026-10-12"


def test_data_con_orario_incollato_senza_separatore():
    lines = ["CAD: 12/10/202614:30"]
    result = extract_date_candidates(lines, today=TODAY)
    assert result.best == "2026-10-12"


def test_data_testuale_con_orario():
    lines = ["CAD 12 OCT 2026 14:30"]
    result = extract_date_candidates(lines, today=TODAY)
    assert result.best == "2026-10-12"


def test_lotto_numerico_non_diventa_una_data():
    assert extract_date_candidates(["2611193080", "003406"]).best is None


def test_data_con_spazi_dopo_i_separatori_e_ora_affiancata():
    assert extract_date_candidates(["19. 11. 2026", "04:24 PJ"]).best == "2026-11-19"


def test_data_oltre_cinque_anni_e_plausibile():
    from datetime import date

    assert extract_date_candidates(["C.P:31/12/2031"], today=date(2026, 10, 11)).best == "2031-12-31"


def test_solo_mese_anno_e_ultimo_giorno_del_mese():
    assert extract_date_candidates(["EXP 11/2027"]).best == "2027-11-30"
