import io
import json
from datetime import date, timedelta
from decimal import Decimal as D
from pathlib import Path

import pytest
from lxml import etree

from sepalast import Creditor, Debit, build_pain008, creditor_id_ok, iban_ok, load_members, sepa_text, validate
from sepalast.core import add_target_days, is_target_day

XSD = etree.XMLSchema(etree.parse(str(Path(__file__).parent / "schemas" / "pain.008.001.08.xsd")))
TODAY = date(2026, 10, 21)
CRED = Creditor(name="Sportverein Grün-Weiß Innsbruck", iban="AT611904300234573201", creditor_id="DE98ZZZ09999999999")

CSV = """Vorname;Nachname;IBAN;Betrag;Mandatsreferenz;Mandatsdatum;Straße;PLZ;Ort;Land;E-Mail
Anna;Müller;AT61 1904 3002 3457 3201;45,00;MITGL-001;15.03.2024;Hauptstraße 1;6020;Innsbruck;AT;anna@example.at
Jürgen;Weiß;DE89370400440532013000;45,00;MITGL-002;01.02.2025;;;;;
Pierre;Favre;CH9300762011623852957;45,00;MITGL-003;01.02.2025;Rue 1;1200;Genève;CH;
Kaputt;Konto;AT611904300234573202;45,00;MITGL-004;01.02.2025;;;;;
Doppelt;Mandat;DE89370400440532013000;30,00;MITGL-001;01.02.2025;;;;;
""".encode("utf-8")


def test_checksums():
    assert creditor_id_ok("DE98ZZZ09999999999") and not creditor_id_ok("DE97ZZZ09999999999")
    assert iban_ok("CH9300762011623852957") and not iban_ok("DE89370400440532013001")


def test_target_days():
    assert not is_target_day(date(2026, 12, 25)) and not is_target_day(date(2026, 4, 3))  # Karfreitag 2026
    assert add_target_days(date(2026, 12, 23), 2) == date(2026, 12, 28)  # 24.12. ist TARGET-Tag


def test_sepa_text():
    assert sepa_text("Grün-Weiß & Co. – Beitrag 2026 €", 70) == "Gruen-Weiss + Co. - Beitrag 2026 EUR"


def test_load_validate_and_xsd():
    debits, m = load_members(CSV, "liste.csv", default_purpose="Mitgliedsbeitrag 2027")
    assert m["iban"] == "IBAN" and debits[0].name == "Anna Müller" and debits[0].amount == D("45.00")
    coll = add_target_days(TODAY, 15)
    head = validate(CRED, debits, coll, today=TODAY)
    assert not [h for h in head if not h.startswith("WARNUNG")]
    errs = {d.mandate_id: d.errors for d in debits}
    assert errs["MITGL-002"] == [] and errs["MITGL-003"] == []  # CH mit Adresse ok
    assert any("IBAN" in e for e in debits[3].errors)
    assert any("doppelt" in e for e in debits[4].errors)
    xml = build_pain008(CRED, debits, coll, "TEST1")
    doc = etree.fromstring(xml)
    XSD.assertValid(doc)
    ns = {"p": "urn:iso:std:iso:20022:tech:xsd:pain.008.001.08"}
    assert doc.findtext(".//p:GrpHdr/p:NbOfTxs", namespaces=ns) == "3"
    assert doc.findtext(".//p:GrpHdr/p:CtrlSum", namespaces=ns) == "135.00"
    assert doc.findtext(".//p:Dbtr/p:Nm", namespaces=ns) == "Anna Mueller"
    assert doc.find(".//p:DrctDbtTxInf[2]/p:Dbtr/p:PstlAdr", namespaces=ns) is None  # ohne Adresse keine Adresse
    assert doc.findtext(".//p:DrctDbtTxInf[1]/p:Dbtr/p:PstlAdr/p:TwnNm", namespaces=ns) == "Innsbruck"


def test_non_eea_without_address_is_error():
    d = Debit(row=2, name="X", iban="CH9300762011623852957", amount=D(10), mandate_id="M1", mandate_date=date(2025, 1, 1))
    validate(CRED, [d], add_target_days(TODAY, 15), today=TODAY)
    assert any("EWR" in e for e in d.errors)


def test_head_errors():
    bad = Creditor(name="", iban="AT00", creditor_id="AT12ZZZ1")
    head = validate(bad, [], TODAY + timedelta(days=1), today=TODAY)
    assert len([h for h in head if not h.startswith("WARNUNG")]) == 4


def test_xlsx_input():
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active
    ws.append(["Name", "IBAN", "Beitrag", "Mandatsreferenz", "Datum der Unterschrift"])
    ws.append(["Eva Berger", "DE89370400440532013000", 25.5, "M-9", date(2024, 5, 1)])
    buf = io.BytesIO(); wb.save(buf)
    debits, _ = load_members(buf.getvalue(), "mitglieder.xlsx")
    assert debits[0].amount == D("25.50") and debits[0].mandate_date == date(2024, 5, 1)


def test_web_bridge():
    from sepalast import web
    cfg = {"name": CRED.name, "iban": CRED.iban, "ci": CRED.creditor_id, "date": add_target_days(date.today(), 15).strftime("%d.%m.%Y"),
           "purpose": "Beitrag"}
    j = json.loads(web.run(CSV, "x.csv", json.dumps(cfg), 2))
    assert j["ok"] and j["limited"] and j["count_ok"] == 2 and j["xml"].startswith("<?xml")
    XSD.assertValid(etree.fromstring(j["xml"].encode()))
    assert "Mandatsreferenz" in web.prenotifications()
