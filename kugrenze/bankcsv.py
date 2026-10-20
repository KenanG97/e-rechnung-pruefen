"""Robuster Leser für Kontoauszug-CSVs österreichischer und deutscher Banken.

Banken exportieren sehr unterschiedlich: Semikolon oder Komma, UTF-8 oder Windows-1252,
deutsches Zahlenformat (1.234,56) oder englisches, Vorspann-Zeilen mit Kontoinfos,
getrennte Soll-/Haben-Spalten. Statt für jede Bank ein festes Schema zu pflegen, sucht der
Leser die Kopfzeile und erkennt die Spalten an typischen Bezeichnungen.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional


class CsvError(Exception):
    pass


@dataclass
class Transaction:
    day: date
    amount: Decimal            # positiv = Eingang
    counterparty: str = ""
    text: str = ""
    row: int = 0
    include: bool = True       # zählt zum Umsatz?
    reason: str = ""           # warum (nicht) gezählt
    tags: list[str] = field(default_factory=list)


DATE_KEYS = ["buchungsdatum", "buchungstag", "valutadatum", "valuta", "wertstellung", "datum", "date", "booking date", "value date", "transaktionsdatum"]
AMOUNT_KEYS = ["betrag", "umsatz in eur", "betrag (eur)", "betrag eur", "amount", "umsatz", "summe", "betrag in eur"]
CREDIT_KEYS = ["haben", "eingang", "gutschrift", "credit"]
DEBIT_KEYS = ["soll", "ausgang", "lastschrift", "belastung", "debit"]
PARTY_KEYS = ["auftraggeber/empfänger", "auftraggeber / empfänger", "zahlungspflichtige", "partnername", "name zahlungsbeteiligter",
              "beguenstigter/zahlungspflichtiger", "begünstigter/zahlungspflichtiger", "empfänger", "auftraggeber", "partner name",
              "payee", "counterparty", "name", "gegenkonto name"]
TEXT_KEYS = ["verwendungszweck", "buchungstext", "umsatztext", "zahlungsreferenz", "beschreibung", "buchungsdetails", "text",
             "reference", "description", "details", "mitteilung", "zweck"]


def _decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise CsvError("Zeichenkodierung nicht erkannt.")


def parse_amount(raw: str) -> Optional[Decimal]:
    s = (raw or "").strip().replace(" ", "").replace(" ", "").replace("€", "").replace("EUR", "").replace("'", "")
    if not s:
        return None
    neg = s.startswith("-") or s.endswith("-") or (s.startswith("(") and s.endswith(")"))
    s = s.strip("+-()")
    if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?|\d+,\d+", s):        # 1.234,56 / 12,5
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", s):               # 1,234.56
        s = s.replace(",", "")
    elif re.fullmatch(r"\d+(\.\d+)?", s):
        pass
    else:
        return None
    try:
        v = Decimal(s)
    except InvalidOperation:
        return None
    return -v if neg else v


def parse_day(raw: str) -> Optional[date]:
    s = (raw or "").strip()[:10]
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y", "%d/%m/%Y", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _find(header: list[str], keys: list[str]) -> Optional[int]:
    norm = [h.strip().strip('"').lower() for h in header]
    for k in keys:  # exakte Treffer zuerst, in Prioritätsreihenfolge
        if k in norm:
            return norm.index(k)
    for k in keys:
        for i, h in enumerate(norm):
            if k in h:
                return i
    return None


def _sniff_delimiter(text: str) -> str:
    sample = "\n".join(text.splitlines()[:40])
    counts = {d: sample.count(d) for d in (";", "\t", ",", "|")}
    return max(counts, key=counts.get)


def parse_csv(data: bytes) -> tuple[list[Transaction], dict]:
    """Gibt Buchungen und erkannte Spaltenzuordnung zurück."""
    if len(data) > 20 * 1024 * 1024:
        raise CsvError("Datei ist größer als 20 MB.")
    text = _decode(data)
    delim = _sniff_delimiter(text)
    rows = list(csv.reader(io.StringIO(text), delimiter=delim))
    if not rows:
        raise CsvError("Die Datei ist leer.")

    # Kopfzeile suchen: erste Zeile, die Datums- und Betragsspalte enthält
    hidx = None
    for i, r in enumerate(rows[:40]):
        if _find(r, DATE_KEYS) is not None and (_find(r, AMOUNT_KEYS) is not None or _find(r, CREDIT_KEYS) is not None):
            hidx = i
            break
    if hidx is None:
        # Ohne Kopfzeile (z. B. George-Export ohne Überschrift): Datum + Betrag per Inhalt erkennen
        return _headerless(rows)
    header = rows[hidx]
    c_date = _find(header, DATE_KEYS)
    c_amt = _find(header, AMOUNT_KEYS)
    c_cr, c_dr = _find(header, CREDIT_KEYS), _find(header, DEBIT_KEYS)
    c_party = _find(header, PARTY_KEYS)
    c_text = _find(header, TEXT_KEYS)
    c_sign = _find(header, ["soll/haben", "s/h", "kennung"])
    if c_amt is not None and c_amt in (c_cr, c_dr):
        c_cr = c_dr = None
    mapping = {"Datum": header[c_date], "Betrag": header[c_amt] if c_amt is not None else f"{header[c_cr]} / {header[c_dr] if c_dr is not None else '–'}",
               "Gegenseite": header[c_party] if c_party is not None else "–", "Text": header[c_text] if c_text is not None else "–",
               "Trennzeichen": {";": "Semikolon", ",": "Komma", "\t": "Tabulator", "|": "Senkrechtstrich"}[delim]}

    tx: list[Transaction] = []
    for n, r in enumerate(rows[hidx + 1:], start=hidx + 2):
        if not r or all(not c.strip() for c in r):
            continue
        get = lambda i: r[i] if i is not None and i < len(r) else ""  # noqa: E731
        d = parse_day(get(c_date))
        if d is None:
            continue  # Summenzeilen, Fußnoten
        if c_amt is not None:
            a = parse_amount(get(c_amt))
            if a is not None and c_sign is not None and get(c_sign).strip().upper() in ("S", "SOLL", "D", "DEBIT"):
                a = -abs(a)
        else:
            cr, dr = parse_amount(get(c_cr)), parse_amount(get(c_dr))
            a = (abs(cr) if cr else Decimal(0)) - (abs(dr) if dr else Decimal(0))
        if a is None:
            continue
        party = get(c_party).strip()
        txt = " ".join(get(c_text).split())
        if c_text is None:  # notfalls alle Textspalten zusammenführen
            txt = " ".join(" ".join(c.split()) for i, c in enumerate(r) if i not in (c_date, c_amt, c_cr, c_dr) and not parse_amount(c) and not parse_day(c))
        tx.append(Transaction(day=d, amount=a, counterparty=party, text=txt, row=n))
    if not tx:
        raise CsvError("Keine Buchungen gefunden. Ist das ein Kontoauszug im CSV-Format?")
    return sorted(tx, key=lambda t: (t.day, t.row)), mapping


def _headerless(rows) -> tuple[list[Transaction], dict]:
    tx = []
    for n, r in enumerate(rows, start=1):
        d = next((parse_day(c) for c in r if parse_day(c)), None)
        amts = [parse_amount(c) for c in r if re.search(r"\d[.,]\d{2}\s*-?$", c.strip())]
        amts = [a for a in amts if a is not None]
        if d is None or not amts:
            continue
        txt = " ".join(c.strip() for c in r if c.strip() and parse_day(c) is None and parse_amount(c) is None)
        tx.append(Transaction(day=d, amount=amts[0], text=txt, row=n))
    if not tx:
        raise CsvError("Spalten nicht erkannt. Die Datei braucht mindestens eine Datums- und eine Betragsspalte.")
    return sorted(tx, key=lambda t: (t.day, t.row)), {"Datum": "automatisch", "Betrag": "automatisch (erste Betragsspalte)",
                                                      "Gegenseite": "–", "Text": "übrige Spalten", "Trennzeichen": "automatisch"}
