import json
from decimal import Decimal as D

import pytest

from shopcheck import load_products, check_product, parse_quantity, unit_price
from shopcheck.products import ShopCsvError

SHOPIFY = b'''Handle,Title,Body (HTML),Vendor,Type,Tags,Published,Option1 Name,Option1 Value,Variant SKU,Variant Grams,Variant Price,Image Src,Unit Price Total Measure,Unit Price Total Measure Unit,Unit Price Base Measure,Unit Price Base Measure Unit
bio-honig,Bio Bluetenhonig 500 g,"<p>Hersteller: Imkerei Gruber, Dorfstrasse 4, 6020 Innsbruck, info@imkerei-gruber.at</p>",Imkerei Gruber,Honig,,true,Title,Default Title,H500,600,9.90,https://x/h.jpg,,,,
oel,Olivenoel,"<p>Hersteller: Oliva SL, Calle Mayor 3, 28001 Madrid, www.oliva.es</p>",Oliva,Oel,,true,Groesse,0.5 l,O05,500,8.00,https://x/o.jpg,500,ml,100,ml
oel,,,,,,,Groesse,1 l,O1,1000,14.00,,1000,ml,1,l
spielzeug,Holz-Steckspiel,"<p>Made in China</p>",ToyCo,Spielzeug,,true,Title,Default Title,T1,300,19.90,https://x/t.jpg,,,,
poster,Poster Alpen 30 x 40 cm,"<p>Hersteller: Druck GmbH, Hauptstr. 1, 10115 Berlin, druck@example.de</p>",Druck GmbH,Poster,,true,Title,Default Title,P1,200,12.00,https://x/p.jpg,,,,
'''

WOO = """ID;Typ;Artikelnummer;Name;Veröffentlicht;Kurzbeschreibung;Beschreibung;Regulärer Preis;Bilder;Marken;GPSR Hersteller
11;simple;K-1;Duftkerze Vanille 200 g;1;;Grundpreis: 74,75 € / 1 kg;14,95;https://x/k.jpg;Kerzenzauber;Kerzenzauber e.U., Lindengasse 8, 1070 Wien, hallo@kerzenzauber.at
12;simple;S-2;Gewürzmischung 3 x 50 g;1;;12,50 € / 100 g;6,00;;Spice;
""".encode("cp1252")

ETSY = b'''TITLE,DESCRIPTION,PRICE,CURRENCY_CODE,QUANTITY,TAGS,MATERIALS,IMAGE1,SKU
"Handgemachte Seife Lavendel","Inhalt: 100 g. Hersteller: Seifenwerk, Bahnhofstr. 2, 4020 Linz, seifenwerk.at",6.50,EUR,10,,,https://x/s.jpg,S1
'''


def codes(fs):
    return {x.code for x in fs}


def test_quantities():
    assert parse_quantity("Honig 500 g")[:2] == (D("0.500"), "kg")
    assert parse_quantity("3 x 50g Tee")[:2] == (D("0.150"), "kg")
    assert parse_quantity("Poster 30 x 40 cm") is None
    assert parse_quantity("Tasse") is None
    assert unit_price(D("9.90"), D("0.5"), "kg") == D("19.80")


def test_shopify_variants_inherit_and_rules():
    ps, m = load_products(SHOPIFY)
    assert m["Plattform"] == "Shopify" and len(ps) == 5
    by = {(p.key, p.variant): p for p in ps}
    honig = by[("bio-honig", "")]
    f, info = check_product(honig)
    assert "GP-1" in codes(f) and info["unit_price_text"] == "19,80 € / 1 kg"
    assert not {"PS-1", "PS-2"} & codes(f)
    oel05 = by[("oel", "0.5 l")]
    assert oel05.vendor == "Oliva" and oel05.title == "Olivenoel"
    f, _ = check_product(oel05)
    assert "GP-3" in codes(f)  # 100 ml als Basis
    f, _ = check_product(by[("oel", "1 l")])
    assert "GP-0" in codes(f)  # genau 1 l
    f, _ = check_product(by[("spielzeug", "")])
    assert {"PS-2", "PS-3", "PS-5"} <= codes(f)
    f, info = check_product(by[("poster", "")])
    assert not any(c.startswith("GP") for c in codes(f)) and "PS-2" not in codes(f)


def test_woocommerce_german_and_existing_unit_prices():
    ps, m = load_products(WOO)
    assert m["Plattform"] == "WooCommerce" and m["Herstellerangaben"] == "GPSR Hersteller"
    f, _ = check_product(ps[0])
    assert not {"GP-1", "GP-2", "GP-3", "PS-1", "PS-2"} & codes(f)   # 14,95/0,2 = 74,75 korrekt
    f, _ = check_product(ps[1])
    assert "GP-3" in codes(f) and "PS-2" in codes(f) and "PS-4" in codes(f)


def test_etsy_labelled_content_in_description():
    ps, m = load_products(ETSY)
    assert m["Plattform"] == "Etsy"
    f, info = check_product(ps[0])
    assert "GP-1" in codes(f) and info["unit_price_text"] == "65,00 € / 1 kg"
    assert "PS-2" not in codes(f)


def test_wrong_unit_price_detected():
    data = b'Name,Preis,Beschreibung,Hersteller\nKaffee 250 g,5.00,"Grundpreis 25,00 EUR / kg. Hersteller X, Weg 1, 1010 Wien, x.at",X\n'
    f, _ = check_product(load_products(data)[0][0])
    assert "GP-2" in codes(f)


def test_errors():
    with pytest.raises(ShopCsvError):
        load_products(b"foo,bar\n1,2\n")


def test_web_bridge_and_export():
    from shopcheck import web
    j = json.loads(web.analyze(SHOPIFY, 3))
    assert j["ok"] and j["summary"]["products"] == 3 and j["summary"]["limited"]
    out = web.export_fixed()
    assert "Grundpreis (berechnet)" in out and "19,80 € / 1 kg" in out
