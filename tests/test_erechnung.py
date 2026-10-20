"""Tests: echte KoSIT-Testrechnungen (positiv) + gezielt manipulierte Varianten (negativ).

Testdaten: https://github.com/itplr-kosit/xrechnung-testsuite (Pfad über XTS_DIR).
"""
import glob
import io
import os
from datetime import date

import pytest
from pypdf import PdfWriter

from erechnung import ParseError, check_against_history, check_invoice, parse_bytes
from erechnung.checks import de_vat_id_valid, iban_valid
from erechnung.export import pdf_report, summary_row, to_csv
from erechnung.store import History, file_hash

XTS = os.environ.get("XTS_DIR", "/tmp/xts/src/test/business-cases")
FILES = sorted(glob.glob(f"{XTS}/*/*.xml"))
CII = f"{XTS}/standard/01.01a-INVOICE_uncefact.xml"
UBL = f"{XTS}/standard/01.01a-INVOICE_ubl.xml"
FUTURE = date(2030, 1, 1)


def codes(fs, sev=None):
    return {f.code for f in fs if sev is None or f.severity == sev}


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.split("/")[-1])
def test_official_samples_have_no_false_errors(path):
    inv = parse_bytes(open(path, "rb").read(), path)
    assert inv.number and inv.seller.name and inv.totals.payable is not None
    errs = codes(check_invoice(inv, FUTURE), "fehler")
    assert not errs, errs


def test_both_syntaxes_give_same_result():
    a = parse_bytes(open(CII, "rb").read())
    b = parse_bytes(open(UBL, "rb").read())
    assert a.syntax == "CII" and b.syntax == "UBL"
    assert a.number == b.number and a.totals.payable == b.totals.payable
    assert a.seller.name == b.seller.name and len(a.lines) == len(b.lines)


def _mutate(path, old, new):
    raw = open(path, "rb").read().decode()
    assert old in raw, old
    return parse_bytes(raw.replace(old, new, 1).encode())


def test_detects_wrong_payable():
    inv = parse_bytes(open(CII, "rb").read())
    good = f"<ram:DuePayableAmount>{inv.totals.payable}</ram:DuePayableAmount>"
    bad = _mutate(CII, good, "<ram:DuePayableAmount>9999.99</ram:DuePayableAmount>")
    assert "R-8" in codes(check_invoice(bad, FUTURE), "fehler")


def test_detects_missing_seller_tax_id():
    raw = open(CII, "rb").read().decode()
    import re
    raw = re.sub(r"<ram:SpecifiedTaxRegistration>.*?</ram:SpecifiedTaxRegistration>", "", raw, flags=re.S)
    assert "P-5" in codes(check_invoice(parse_bytes(raw.encode()), FUTURE), "fehler")


def test_detects_minimum_profile():
    raw = open(CII, "rb").read().decode()
    inv = parse_bytes(raw.encode())
    raw = raw.replace(inv.guideline, "urn:factur-x.eu:1p0:minimum")
    assert "FMT-2" in codes(check_invoice(parse_bytes(raw.encode()), FUTURE), "fehler")


def test_iban_and_vat_checksums():
    assert iban_valid("DE89 3704 0044 0532 0130 00")
    assert not iban_valid("DE89 3704 0044 0532 0130 01")
    assert iban_valid("AT611904300234573201")
    assert de_vat_id_valid("DE143454214") is True
    assert de_vat_id_valid("DE123456789") is False
    assert de_vat_id_valid("ATU12345678") is None


def test_zugferd_pdf_roundtrip_and_plain_pdf_rejected():
    xml = open(CII, "rb").read()
    w = PdfWriter()
    w.add_blank_page(595, 842)
    plain = io.BytesIO()
    w.write(plain)
    with pytest.raises(ParseError, match="keine eingebetteten"):
        parse_bytes(plain.getvalue())
    w.add_attachment("factur-x.xml", xml)
    zf = io.BytesIO()
    w.write(zf)
    inv = parse_bytes(zf.getvalue(), "test.pdf")
    assert inv.container.startswith("PDF") and inv.number


def test_rejects_garbage_and_xxe():
    with pytest.raises(ParseError):
        parse_bytes(b"hello world")
    xxe = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><x>&e;</x>'
    with pytest.raises(ParseError):
        parse_bytes(xxe)


def test_history_detects_iban_change_and_duplicate(tmp_path):
    h = History(tmp_path / "h.db")
    raw = open(CII, "rb").read()
    inv = parse_bytes(raw)
    inv._hash = file_hash(raw)
    if not inv.iban:
        inv.iban = "DE89370400440532013000"
    h.add(inv, "gelb", 0, 1)
    # gleiche Nummer, andere Datei, neue IBAN -> Duplikat + IBAN-Wechsel
    inv2 = parse_bytes(raw)
    inv2._hash = "anders"
    inv2.iban = "LT121000011101001000"
    fs = check_against_history(inv2, h.all())
    assert {"H-1", "H-2"} <= codes(fs)


def test_exports():
    inv = parse_bytes(open(UBL, "rb").read(), "x.xml")
    fs = check_invoice(inv, FUTURE)
    assert pdf_report(inv, fs, "Test")[:5] == b"%PDF-"
    assert "Lieferant".encode() in to_csv([summary_row(inv, "gelb")])


def test_license_keys():
    from erechnung.license import make_key, verify_key
    k = make_key("kunde@firma.de", "2027-12-31", secret=b"s")
    assert verify_key(k, date(2027, 1, 1), secret=b"s") == (True, "kunde@firma.de")
    assert not verify_key(k, date(2028, 1, 1), secret=b"s")[0]
    assert not verify_key(k, date(2027, 1, 1), secret=b"other")[0]
    assert not verify_key(k[:-2] + "AA", date(2027, 1, 1), secret=b"s")[0]
