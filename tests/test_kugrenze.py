from datetime import date
from decimal import Decimal as D

import pytest

from kugrenze import CsvError, evaluate, parse_csv
from kugrenze.bankcsv import Transaction, parse_amount, parse_day
from kugrenze.rules import classify


def tx(*items):
    return [Transaction(day=date.fromisoformat(d), amount=D(str(a)), text=t) for d, a, t in items]


# ---------------------------------------------------------------- CSV-Formate

GEORGE_LIKE = """Buchungsdatum;Partnername;Partner IBAN;Buchungs-Details;Betrag;Währung
02.01.2026;Muster GmbH;AT611904300234573201;Rechnung 2026-001;1.250,00;EUR
05.01.2026;Billa AG;;Einkauf;-45,30;EUR
10.01.2026;Finanzamt Innsbruck;;Arbeitnehmerveranlagung 2025;312,00;EUR
""".encode("cp1252")

SPARKASSE_LIKE = b'''"Auftragskonto";"Buchungstag";"Valutadatum";"Buchungstext";"Verwendungszweck";"Beguenstigter/Zahlungspflichtiger";"Kontonummer/IBAN";"Betrag";"Waehrung"
"DE123";"03.02.26";"03.02.26";"GUTSCHR. UEBERWEISUNG";"RE 17 Webdesign";"Kunde AG";"DE89370400440532013000";"2.380,00";"EUR"
"DE123";"04.02.26";"04.02.26";"LASTSCHRIFT";"Miete";"Vermieter";"DE00";"-800,00";"EUR"
'''

N26_LIKE = b"""Date,Payee,Account number,Transaction type,Payment reference,Amount (EUR),Amount (Foreign Currency),Type Foreign Currency,Exchange Rate
2026-03-01,PayPal Europe,,Credit Transfer,PayPal Auszahlung,512.40,,,
2026-03-02,Max Mustermann,,Credit Transfer,Umbuchung Tagesgeld,1000.00,,,
2026-03-05,Klient Studio,,Credit Transfer,Invoice 42,"1,500.00",,,
"""

SOLL_HABEN = """Kontoinhaber: Max Muster
Zeitraum: 01.01.2026 - 31.03.2026

Datum;Text;Soll;Haben
15.01.2026;Honorar Projekt A;;900,00
16.01.2026;Bürobedarf;35,00;
""".encode()


def test_george_like_cp1252_and_classification():
    t, m = parse_csv(GEORGE_LIKE)
    assert m["Betrag"] == "Betrag" and len(t) == 3
    classify(t)
    inc = [x for x in t if x.include]
    assert [x.amount for x in inc] == [D("1250.00")]
    assert next(x for x in t if "Finanzamt" in x.counterparty).reason == "Steuererstattung"


def test_sparkasse_like_quotes_two_digit_year():
    t, _ = parse_csv(SPARKASSE_LIKE)
    assert t[0].day == date(2026, 2, 3) and t[0].amount == D("2380.00") and t[0].counterparty == "Kunde AG"
    assert t[1].amount == D("-800.00")


def test_n26_like_comma_english_numbers_platform_and_own_transfer():
    t, _ = parse_csv(N26_LIKE)
    classify(t, ["Max Mustermann"])
    by = {x.counterparty: x for x in t}
    assert by["Klient Studio"].amount == D("1500.00") and by["Klient Studio"].include
    assert "plattform" in by["PayPal Europe"].tags and by["PayPal Europe"].include
    assert not by["Max Mustermann"].include


def test_soll_haben_with_preamble():
    t, _ = parse_csv(SOLL_HABEN)
    assert [x.amount for x in t] == [D("900.00"), D("-35.00")]


def test_rejects_non_csv():
    with pytest.raises(CsvError):
        parse_csv(b"hallo welt\nnichts hier")


@pytest.mark.parametrize("raw,val", [("1.234,56", "1234.56"), ("-1.234,56", "-1234.56"), ("1,234.56", "1234.56"),
                                     ("12,5", "12.5"), ("100", "100"), ("50,00-", "-50.00"), ("€ 7,00", "7.00")])
def test_amounts(raw, val):
    assert parse_amount(raw) == D(val)


def test_dates():
    assert parse_day("31.12.2025") == date(2025, 12, 31) and parse_day("2026-01-02") == date(2026, 1, 2)


# ---------------------------------------------------------------- Österreich

def test_at_exactly_at_limit_is_green():
    r = evaluate(tx(("2026-06-30", 55000, "")), "AT", 2026, as_of=date(2026, 12, 31))
    assert r["status"] == "gruen"


def test_at_within_tolerance_is_yellow_next_year():
    r = evaluate(tx(("2026-03-01", 50000, ""), ("2026-10-01", 10500, "")), "AT", 2026)
    assert r["status"] == "gelb" and "bis 31.12.2026" in r["headline"]


def test_at_over_tolerance_immediately_from_that_transaction():
    r = evaluate(tx(("2026-03-01", 50000, ""), ("2026-08-01", 10000, ""), ("2026-09-15", 600, "")), "AT", 2026)
    assert r["status"] == "rot" and r["crossed_on"] == date(2026, 9, 15)


def test_at_prior_year_over_limit():
    r = evaluate(tx(("2026-01-05", 100, "")), "AT", 2026, prior_year_turnover=D(56000))
    assert r["status"] == "rot" and "Vorjahr" in r["detail"]


def test_at_prior_year_computed_from_full_year_data():
    items = [(f"2025-{m:02d}-10", 5000, "") for m in range(1, 13)] + [("2026-01-10", 100, "")]
    r = evaluate(tx(*items), "AT", 2026)
    assert r["prior_year_turnover"] == D(60000) and r["status"] == "rot"


def test_at_forecast_warns():
    r = evaluate(tx(("2026-01-31", 10000, ""), ("2026-03-31", 10000, "")), "AT", 2026)
    # 20.000 in 90 Tagen -> ~81.000 hochgerechnet
    assert r["status"] == "gelb" and r["forecast"] > 55000 and r["forecast_hit"].year == 2026


# ---------------------------------------------------------------- Deutschland

def test_de_under_25k_green():
    r = evaluate(tx(("2026-12-01", 20000, "")), "DE", 2026, prior_year_turnover=D(10000))
    assert r["status"] == "gruen"


def test_de_over_25k_yellow_next_year():
    r = evaluate(tx(("2026-12-01", 30000, "")), "DE", 2026, prior_year_turnover=D(10000))
    assert r["status"] == "gelb" and "ab 2027" in r["headline"]


def test_de_over_100k_immediately():
    r = evaluate(tx(("2026-05-01", 99999.99, ""), ("2026-06-01", 0.02, "")), "DE", 2026, prior_year_turnover=D(20000))
    assert r["status"] == "rot" and r["crossed_on"] == date(2026, 6, 1)


def test_de_prior_over_25k():
    r = evaluate([], "DE", 2026, prior_year_turnover=D(25000.01))
    assert r["status"] == "rot"


def test_de_founding_year_25k_immediately():
    r = evaluate(tx(("2026-07-01", 20000, ""), ("2026-09-01", 6000, "")), "DE", 2026, founding_year=True)
    assert r["status"] == "rot" and r["crossed_on"] == date(2026, 9, 1)


def test_extra_turnover_counts():
    r = evaluate(tx(("2026-02-01", 50000, "")), "AT", 2026, extra_turnover=D(11000))
    assert r["turnover"] == D(61000) and r["status"] == "rot"


def test_web_bridge_roundtrip():
    import json
    from kugrenze import web
    web.reset()
    j = json.loads(web.load(GEORGE_LIKE))
    assert j["ok"] and j["years"] == [2026]
    out = json.loads(web.run("AT", 2026))
    assert out["result"]["turnover"] == 1250.0
    fa = next(x for x in out["transactions"] if "Finanzamt" in x["party"])
    web.toggle(fa["i"], True)
    assert json.loads(web.run("AT", 2026))["result"]["turnover"] == 1562.0


def test_past_year_not_extrapolated_and_manual_mode():
    r = evaluate(tx(("2025-06-01", 20000, ""), ("2026-01-05", 10, "")), "AT", 2025)
    assert r["forecast_hit"] is None and r["as_of"] == date(2025, 12, 31)
    r = evaluate([], "AT", 2026, extra_turnover=D(40000))
    assert r["status"] == "gruen" and r["forecast_hit"] is None
