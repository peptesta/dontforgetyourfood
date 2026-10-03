import pytest

from app.services.image_storage import LocalDiskImageStorage


def test_save_e_load_roundtrip(tmp_path):
    storage = LocalDiskImageStorage(tmp_path)
    storage.save("household1/item1.jpg", b"contenuto finto jpeg")
    assert storage.load("household1/item1.jpg") == b"contenuto finto jpeg"


def test_load_chiave_inesistente_ritorna_none(tmp_path):
    storage = LocalDiskImageStorage(tmp_path)
    assert storage.load("non/esiste.jpg") is None


def test_delete_rimuove_il_file(tmp_path):
    storage = LocalDiskImageStorage(tmp_path)
    storage.save("h/item.jpg", b"dati")
    storage.delete("h/item.jpg")
    assert storage.load("h/item.jpg") is None


def test_delete_chiave_inesistente_non_esplode(tmp_path):
    storage = LocalDiskImageStorage(tmp_path)
    storage.delete("non/esiste.jpg")  # non deve sollevare


def test_rifiuta_path_traversal(tmp_path):
    storage = LocalDiskImageStorage(tmp_path)
    with pytest.raises(ValueError):
        storage.save("../../etc/passwd", b"dati")
    with pytest.raises(ValueError):
        storage.save("household1/../../../etc/passwd", b"dati")
