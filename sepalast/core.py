"""SEPA-Lastschrift (CORE) im Format pain.008.001.08 erzeugen und prüfen.

Hintergrund: Viele Banken akzeptieren ab November 2026 für Lastschrift-Dateien nur noch
pain.008.001.08 (ISO 20022 Version 2019); das ältere pain.008.001.02 läuft aus. Adressen müssen,
wenn angegeben, strukturiert oder hybrid sein (mindestens Ort `TwnNm` und Land `Ctry`).
Die Adresse des Zahlers ist Pflicht, wenn sein Konto außerhalb des EWR liegt (z. B. CH, GB).

Bewusst ohne Fremdbibliotheken (nur Standardbibliothek), damit es auch im Browser läuft.
"""
from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

NS = "urn:iso:std:iso:20022:tech:xsd:pain.008.001.08"
D = Decimal
# EWR-Staaten (inkl. französischer Überseegebiete und Åland). Nicht-EWR-SEPA-Länder sind z. B.
# CH, GB, SM, MC, VA, AD, GI, JE, GG, IM, AL, MD, ME, MK, RS – dort ist die Zahleradresse Pflicht.
EEA = set("AT BE BG HR CY CZ DK EE FI FR DE GR HU IS IE IT LV LI LT LU MT NL NO PL PT RO SK SI ES SE".split()) | {
    "GF", "GP", "MQ", "YT", "RE", "PM", "MF", "BL", "AX"}


# ---------------------------------------------------------------- Prüfziffern & Zeichen

def clean_iban(s: str) -> str:
    return re.sub(r"\s+", "", s or "").upper()


def iban_ok(iban: str) -> bool:
    s = clean_iban(iban)
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", s):
        return False
    lengths = {"AT": 20, "DE": 22, "CH": 21, "LI": 21, "IT": 27, "FR": 27, "NL": 18, "BE": 16, "LU": 20, "ES": 24, "GB": 22}
    if s[:2] in lengths and len(s) != lengths[s[:2]]:
        return False
    return int("".join(str(int(c, 36)) for c in s[4:] + s[:4])) % 97 == 1


def creditor_id_ok(ci: str) -> bool:
    """Gläubiger-Identifikationsnummer, z. B. DE98ZZZ09999999999 oder ATxxZZZ00000000000."""
    s = re.sub(r"\s+", "", ci or "").upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{3}[A-Z0-9]{1,28}", s):
        return False
    if s[:2] == "DE" and len(s) != 18:
        return False
    if s[:2] == "AT" and len(s) != 18:
        return False
    national = s[7:]
    digits = "".join(str(int(c, 36)) for c in national + s[:2] + "00")
    return 98 - int(digits) % 97 == int(s[2:4])


def bic_ok(bic: str) -> bool:
    return bool(re.fullmatch(r"[A-Z]{6}[A-Z2-9][A-NP-Z0-9]([A-Z0-9]{3})?", (bic or "").replace(" ", "").upper()))


_TRANS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss", "&": "+", "€": "EUR",
                        "–": "-", "—": "-", "„": "'", "“": "'", "”": "'", "‚": "'", "‘": "'", "’": "'", "_": "-", "@": "(at)"})
_ALLOWED = re.compile(r"[^A-Za-z0-9/\-?:().,'+ ]")


def sepa_text(s: str, maxlen: int) -> str:
    """Auf den EPC-Basiszeichensatz abbilden (Umlaute ausschreiben, Rest entfernen)."""
    s = (s or "").translate(_TRANS)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = _ALLOWED.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()[:maxlen]


MANDATE_RE = re.compile(r"[A-Za-z0-9+?/\-:().,']{1,35}")


# ---------------------------------------------------------------- Bankarbeitstage (TARGET2)

def _easter(y: int) -> date:
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(y, month, day)


def is_target_day(d: date) -> bool:
    if d.weekday() >= 5:
        return False
    e = _easter(d.year)
    return d not in {date(d.year, 1, 1), e - timedelta(days=2), e + timedelta(days=1), date(d.year, 5, 1),
                     date(d.year, 12, 25), date(d.year, 12, 26)}


def add_target_days(d: date, n: int) -> date:
    while n > 0:
        d += timedelta(days=1)
        if is_target_day(d):
            n -= 1
    return d


def next_target_day(d: date) -> date:
    while not is_target_day(d):
        d += timedelta(days=1)
    return d


# ---------------------------------------------------------------- Daten

@dataclass
class Creditor:
    name: str
    iban: str
    creditor_id: str
    bic: str = ""
    town: str = ""
    country: str = ""


@dataclass
class Debit:
    row: int
    name: str
    iban: str
    amount: Optional[Decimal]
    mandate_id: str
    mandate_date: Optional[date]
    purpose: str = ""
    bic: str = ""
    street: str = ""
    postcode: str = ""
    town: str = ""
    country: str = ""
    email: str = ""
    seq: str = "RCUR"
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate(cred: Creditor, debits: list[Debit], collection: date, today: Optional[date] = None) -> list[str]:
    """Prüft alles; gibt Fehler der Kopfdaten zurück, Positionsfehler landen in den Debits."""
    today = today or date.today()
    head: list[str] = []
    if not sepa_text(cred.name, 70):
        head.append("Name des Zahlungsempfängers (Verein) fehlt.")
    if not iban_ok(cred.iban):
        head.append(f"IBAN des Vereinskontos „{cred.iban}“ ist ungültig.")
    if not creditor_id_ok(cred.creditor_id):
        head.append(f"Gläubiger-ID „{cred.creditor_id}“ ist ungültig (Format z. B. AT12ZZZ00000000001 bzw. DE98ZZZ09999999999, Prüfziffer prüfen).")
    if cred.bic and not bic_ok(cred.bic):
        head.append(f"BIC „{cred.bic}“ des Vereinskontos hat ein ungültiges Format.")
    earliest = add_target_days(today, 2)
    if collection < earliest:
        head.append(f"Einzugsdatum {collection:%d.%m.%Y} ist zu früh. Frühestens möglich (sicher): {earliest:%d.%m.%Y} – "
                    "die Datei muss spätestens einen Bankarbeitstag vor Fälligkeit bei der Bank sein, viele Banken verlangen mehr.")
    elif not is_target_day(collection):
        head.append(f"Einzugsdatum {collection:%d.%m.%Y} ist kein Bankarbeitstag. Nächster möglicher Tag: {next_target_day(collection):%d.%m.%Y}.")
    if (collection - today).days < 14:
        head.append("WARNUNG: Die Vorabankündigung (Pre-Notification) muss Zahler grundsätzlich 14 Kalendertage vor Fälligkeit erreichen, "
                    "sofern Sie keine kürzere Frist vereinbart haben (z. B. in der Satzung oder im Mandat).")
    seen_m: dict[str, int] = {}
    for d in debits:
        if not sepa_text(d.name, 70):
            d.errors.append("Name fehlt.")
        if not iban_ok(d.iban):
            d.errors.append(f"IBAN „{d.iban}“ ungültig.")
        if d.bic and not bic_ok(d.bic):
            d.warnings.append(f"BIC „{d.bic}“ ungültig – wird weggelassen (bei IBAN im EWR nicht nötig).")
            d.bic = ""
        if d.amount is None or d.amount <= 0:
            d.errors.append("Betrag fehlt oder ist nicht positiv.")
        elif d.amount > D("999999999.99"):
            d.errors.append("Betrag zu hoch.")
        elif d.amount != d.amount.quantize(D("0.01")):
            d.warnings.append(f"Betrag {d.amount} auf Cent gerundet.")
            d.amount = d.amount.quantize(D("0.01"), rounding=ROUND_HALF_UP)
        if not d.mandate_id:
            d.errors.append("Mandatsreferenz fehlt.")
        elif not MANDATE_RE.fullmatch(d.mandate_id):
            d.errors.append(f"Mandatsreferenz „{d.mandate_id}“ enthält unzulässige Zeichen oder ist länger als 35 Zeichen.")
        else:
            key = d.mandate_id.upper()
            if key in seen_m:
                d.errors.append(f"Mandatsreferenz „{d.mandate_id}“ doppelt (auch Zeile {seen_m[key]}).")
            seen_m[key] = d.row
        if d.mandate_date is None:
            d.errors.append("Datum der Mandatsunterschrift fehlt.")
        elif d.mandate_date > today:
            d.errors.append(f"Mandatsdatum {d.mandate_date:%d.%m.%Y} liegt in der Zukunft.")
        elif d.mandate_date < today - timedelta(days=3 * 365):
            d.warnings.append("Mandat älter als 36 Monate: Es verfällt, wenn es 36 Monate nicht genutzt wurde. Nur weiterverwenden, "
                              "wenn in dieser Zeit eingezogen wurde.")
        ctry = clean_iban(d.iban)[:2]
        if d.country and not re.fullmatch(r"[A-Za-z]{2}", d.country):
            d.warnings.append(f"Land „{d.country}“ ist kein ISO-Ländercode (z. B. AT, DE) – Adresse wird weggelassen.")
            d.country = ""
        if ctry and ctry not in EEA:
            if not (d.town and (d.country or ctry)):
                d.errors.append(f"Konto außerhalb des EWR ({ctry}): Adresse des Zahlers (mindestens Ort und Land) ist Pflicht.")
            if not d.bic:
                d.warnings.append(f"Konto außerhalb des EWR ({ctry}): BIC angeben, viele Banken verlangen ihn.")
        if (d.street or d.postcode) and not d.town:
            d.warnings.append("Adresse ohne Ort – wird weggelassen (Ort und Land sind Pflicht, wenn eine Adresse angegeben wird).")
    return head


# ---------------------------------------------------------------- XML

def _sub(parent, tag, text=None, **attrs):
    el = ET.SubElement(parent, f"{{{NS}}}{tag}", attrs)
    if text is not None:
        el.text = text
    return el


def _addr(parent, street, postcode, town, country):
    if not town:
        return
    a = _sub(parent, "PstlAdr")
    if street:
        _sub(a, "StrtNm", sepa_text(street, 70))
    if postcode:
        _sub(a, "PstCd", sepa_text(postcode, 16))
    _sub(a, "TwnNm", sepa_text(town, 35))
    _sub(a, "Ctry", country.upper())


def _agent(parent, bic):
    fi = _sub(parent, "FinInstnId")
    if bic:
        _sub(fi, "BICFI", bic.replace(" ", "").upper())
    else:
        _sub(_sub(fi, "Othr"), "Id", "NOTPROVIDED")


def build_pain008(cred: Creditor, debits: list[Debit], collection: date, msg_id: str, now: Optional[datetime] = None,
                  batch_booking: bool = True) -> bytes:
    """Erzeugt die XML-Datei. Positionen mit Fehlern werden NICHT aufgenommen."""
    now = now or datetime.now()
    ok = [d for d in debits if not d.errors]
    if not ok:
        raise ValueError("Keine fehlerfreien Lastschriften.")
    ET.register_namespace("", NS)
    doc = ET.Element(f"{{{NS}}}Document")
    root = _sub(doc, "CstmrDrctDbtInitn")
    total = sum((d.amount for d in ok), D(0))
    gh = _sub(root, "GrpHdr")
    _sub(gh, "MsgId", sepa_text(msg_id, 35))
    _sub(gh, "CreDtTm", now.strftime("%Y-%m-%dT%H:%M:%S"))
    _sub(gh, "NbOfTxs", str(len(ok)))
    _sub(gh, "CtrlSum", f"{total:.2f}")
    _sub(_sub(gh, "InitgPty"), "Nm", sepa_text(cred.name, 70))

    by_seq: dict[str, list[Debit]] = {}
    for d in ok:
        by_seq.setdefault(d.seq, []).append(d)
    for n, (seq, items) in enumerate(sorted(by_seq.items()), start=1):
        pi = _sub(root, "PmtInf")
        _sub(pi, "PmtInfId", sepa_text(f"{msg_id}-{n}", 35))
        _sub(pi, "PmtMtd", "DD")
        _sub(pi, "BtchBookg", "true" if batch_booking else "false")
        _sub(pi, "NbOfTxs", str(len(items)))
        _sub(pi, "CtrlSum", f"{sum(d.amount for d in items):.2f}")
        pt = _sub(pi, "PmtTpInf")
        _sub(_sub(pt, "SvcLvl"), "Cd", "SEPA")
        _sub(_sub(pt, "LclInstrm"), "Cd", "CORE")
        _sub(pt, "SeqTp", seq)
        _sub(pi, "ReqdColltnDt", collection.isoformat())
        cd = _sub(pi, "Cdtr")
        _sub(cd, "Nm", sepa_text(cred.name, 70))
        _addr(cd, "", "", cred.town, cred.country or clean_iban(cred.iban)[:2])
        _sub(_sub(_sub(pi, "CdtrAcct"), "Id"), "IBAN", clean_iban(cred.iban))
        _agent(_sub(pi, "CdtrAgt"), cred.bic)
        _sub(pi, "ChrgBr", "SLEV")
        sch = _sub(_sub(_sub(_sub(pi, "CdtrSchmeId"), "Id"), "PrvtId"), "Othr")
        _sub(sch, "Id", re.sub(r"\s+", "", cred.creditor_id).upper())
        _sub(_sub(sch, "SchmeNm"), "Prtry", "SEPA")
        for i, d in enumerate(items, start=1):
            tx = _sub(pi, "DrctDbtTxInf")
            _sub(_sub(tx, "PmtId"), "EndToEndId", sepa_text(f"{d.mandate_id}-{collection:%Y%m%d}", 35))
            _sub(tx, "InstdAmt", f"{d.amount:.2f}", Ccy="EUR")
            m = _sub(_sub(tx, "DrctDbtTx"), "MndtRltdInf")
            _sub(m, "MndtId", d.mandate_id)
            _sub(m, "DtOfSgntr", d.mandate_date.isoformat())
            _agent(_sub(tx, "DbtrAgt"), d.bic)
            db = _sub(tx, "Dbtr")
            _sub(db, "Nm", sepa_text(d.name, 70))
            _addr(db, d.street, d.postcode, d.town, d.country or clean_iban(d.iban)[:2])
            _sub(_sub(_sub(tx, "DbtrAcct"), "Id"), "IBAN", clean_iban(d.iban))
            if d.purpose:
                _sub(_sub(tx, "RmtInf"), "Ustrd", sepa_text(d.purpose, 140))
    ET.indent(doc, space="  ")
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(doc, encoding="utf-8")


def prenotification_text(cred: Creditor, d: Debit, collection: date) -> str:
    iban = clean_iban(d.iban)
    masked = iban[:4] + " **** " + iban[-4:]
    amt = f"{d.amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return (f"Liebe/r {d.name},\n\nwir ziehen am {collection:%d.%m.%Y} den Betrag von {amt} EUR"
            f"{' für ' + d.purpose if d.purpose else ''} per SEPA-Lastschrift von Ihrem Konto {masked} ein.\n"
            f"Mandatsreferenz: {d.mandate_id}\nGläubiger-ID: {cred.creditor_id}\n\nBitte sorgen Sie für ausreichende Kontodeckung.\n\n"
            f"Mit freundlichen Grüßen\n{cred.name}")
