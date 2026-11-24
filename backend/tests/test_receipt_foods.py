from app.services.receipt.foods import is_non_food, load_fresh_products
from app.services.receipt.matching import is_reliable, match_catalog


def test_riconosce_prodotti_non_alimentari():
    for nome in ["ARNES PERRO", "PIJAMA MUJER", "GEL DE BAÑO", "PAPEL HIGIENICO", "DETERGENTE ROPA", "CHAMPU ANTICASPA"]:
        assert is_non_food(nome), nome


def test_i_prodotti_alimentari_restano():
    for nome in ["GELATINA FRESA", "CREMAS DE HORTALIZAS", "AGUA MINERAL NATURAL", "PECHUGA DE POLLO", "PASTA DE ALMENDRAS", "BANANA"]:
        assert not is_non_food(nome), nome


def test_lista_freschi_ha_voci_generiche_con_flag():
    fresh = load_fresh_products()
    assert len(fresh) > 200
    assert all(p["fresco"] is True and p["generico"] is True and p["brand"] == "" for p in fresh)


def test_freschi_generici_vengono_abbinati_con_flag_fresco():
    products = load_fresh_products()
    for nome in ["BANANA", "KIWI VERDE CESTA", "UVA BLANCA SIN SEM", "PATATA GRANEL", "LANGOSTINO COCIDO", "BAGUETIN"]:
        best = match_catalog(nome, products=products)[0]
        assert is_reliable(best), (nome, best)
        assert best.fresco is True
