"""Prüfungen aus Sicht des Rechnungs-EMPFÄNGERS.

Ziel ist nicht, die offizielle KoSIT-Validierung (Schematron, mehrere hundert Regeln)
nachzubauen, sondern die Fragen zu beantworten, die einen kleinen Betrieb wirklich
Geld kosten:

1. Sind die Pflichtangaben nach § 14 Abs. 4 UStG vorhanden? (Sonst wackelt der Vorsteuerabzug.)
2. Stimmen die Summen? (Rechenfehler -> falscher Betrag gezahlt / falsche Vorsteuer.)
3. Ist die Bankverbindung plausibel – und hat sie sich gegenüber früheren Rechnungen
   desselben Lieferanten geändert? (Häufigstes Muster beim Rechnungsbetrug.)
4. Ist die Rechnung ein Duplikat?

Jeder Befund hat einen Schweregrad: "fehler" (handeln!), "warnung" (prüfen) oder "info".
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Optional

from .model import Invoice

CENT = Decimal("0.01")
TOL = Decimal("0.01")


@dataclass
class Finding:
    severity: str   # "fehler" | "warnung" | "info"
    code: str
    message: str
    legal: str = ""

    @property
    def icon(self) -> str:
        return {"fehler": "❌", "warnung": "⚠️", "info": "ℹ️"}[self.severity]


def _m(x) -> str:
    """Betrag deutsch formatiert: 1.336,90"""
    return f"{Decimal(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _r(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------- Formatprüfungen

def iban_valid(iban: str) -> bool:
    """ISO 13616 Prüfziffer (Modulo 97)."""
    s = re.sub(r"\s+", "", iban or "").upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}", s):
        return False
    if s.startswith("DE") and len(s) != 22:
        return False
    if s.startswith("AT") and len(s) != 20:
        return False
    rearranged = s[4:] + s[:4]
    digits = "".join(str(int(c, 36)) for c in rearranged)
    return int(digits) % 97 == 1


def de_vat_id_valid(vat: str) -> Optional[bool]:
    """Formal- und Prüfzifferntest für deutsche USt-IdNr. (Verfahren nach ISO 7064, MOD 11,10).

    Gibt None zurück, wenn es keine deutsche USt-IdNr. ist (andere Länder: nur Formatprüfung).
    """
    s = re.sub(r"\s+", "", vat or "").upper()
    if not s.startswith("DE"):
        return None
    if not re.fullmatch(r"DE\d{9}", s):
        return False
    digits = s[2:]
    product = 10
    for d in digits[:8]:
        total = (int(d) + product) % 10
        if total == 0:
            total = 10
        product = (total * 2) % 11
    check = 11 - product
    if check == 10:
        check = 0
    return check == int(digits[8])


EU_VAT_PATTERNS = {
    "AT": r"ATU\d{8}", "BE": r"BE[01]\d{9}", "BG": r"BG\d{9,10}", "CY": r"CY\d{8}[A-Z]",
    "CZ": r"CZ\d{8,10}", "DE": r"DE\d{9}", "DK": r"DK\d{8}", "EE": r"EE\d{9}",
    "EL": r"EL\d{9}", "ES": r"ES[A-Z0-9]\d{7}[A-Z0-9]", "FI": r"FI\d{8}",
    "FR": r"FR[A-HJ-NP-Z0-9]{2}\d{9}", "HR": r"HR\d{11}", "HU": r"HU\d{8}",
    "IE": r"IE\d{7}[A-W][A-I]?|IE\d[A-Z+*]\d{5}[A-W]", "IT": r"IT\d{11}",
    "LT": r"LT(\d{9}|\d{12})", "LU": r"LU\d{8}", "LV": r"LV\d{11}", "MT": r"MT\d{8}",
    "NL": r"NL\d{9}B\d{2}", "PL": r"PL\d{10}", "PT": r"PT\d{9}", "RO": r"RO\d{2,10}",
    "SE": r"SE\d{12}", "SI": r"SI\d{8}", "SK": r"SK\d{10}", "XI": r"XI(\d{9}|\d{12}|GD\d{3}|HA\d{3})",
}


def vat_id_format_ok(vat: str) -> Optional[bool]:
    s = re.sub(r"[\s.\-]", "", vat or "").upper()
    if len(s) < 4:
        return False
    pat = EU_VAT_PATTERNS.get(s[:2])
    if pat is None:
        return None  # Nicht-EU: keine Aussage
    return re.fullmatch(pat, s) is not None


# ---------------------------------------------------------------- Hauptprüfung

def check_invoice(inv: Invoice, today: Optional[date] = None) -> list[Finding]:
    today = today or date.today()
    f: list[Finding] = []
    add = lambda sev, code, msg, legal="": f.append(Finding(sev, code, msg, legal))  # noqa: E731

    # --- Format / Standard
    if not inv.guideline:
        add("warnung", "FMT-1", "Keine Spezifikationskennung (BT-24) angegeben – unklar, nach welchem Standard die Rechnung erstellt wurde.")
    elif "en16931" not in inv.guideline.lower().replace(" ", "") and "xrechnung" not in inv.guideline.lower():
        low = inv.guideline.lower()
        if "minimum" in low or "basicwl" in low:
            add("fehler", "FMT-2",
                "Profil MINIMUM bzw. BASIC WL: Diese ZUGFeRD-Profile enthalten keine Rechnungspositionen und gelten "
                "in Deutschland nicht als E-Rechnung im Sinne von § 14 UStG. Lassen Sie sich eine Rechnung im Profil "
                "EN 16931 (COMFORT), EXTENDED oder XRechnung schicken.", "BMF-Schreiben v. 15.10.2024 zur E-Rechnung")
        elif "extended" in low:
            add("info", "FMT-3", "Profil EXTENDED – zulässig, enthält ggf. Zusatzfelder außerhalb der EN 16931.")
        else:
            add("info", "FMT-4", f"Spezifikation: {inv.guideline}")

    # --- Pflichtangaben § 14 Abs. 4 UStG
    legal = "§ 14 Abs. 4 UStG"
    if not inv.seller.name:
        add("fehler", "P-1", "Name des Lieferanten fehlt.", legal + " Nr. 1")
    if inv.seller.address.is_empty() or not inv.seller.address.city:
        add("fehler", "P-2", "Vollständige Anschrift des Lieferanten fehlt.", legal + " Nr. 1")
    if not inv.buyer.name:
        add("fehler", "P-3", "Name des Leistungsempfängers (also Ihr Name) fehlt.", legal + " Nr. 1")
    if inv.buyer.address.is_empty() or not inv.buyer.address.city:
        add("warnung", "P-4", "Anschrift des Leistungsempfängers ist unvollständig.", legal + " Nr. 1")
    if not (inv.seller.vat_id or inv.seller.tax_number):
        add("fehler", "P-5", "Weder Steuernummer noch USt-IdNr. des Lieferanten angegeben.", legal + " Nr. 2")
    if not inv.issue_date:
        add("fehler", "P-6", "Rechnungsdatum fehlt.", legal + " Nr. 3")
    elif inv.issue_date > today:
        add("warnung", "P-6b", f"Rechnungsdatum {inv.issue_date:%d.%m.%Y} liegt in der Zukunft.")
    if not inv.number:
        add("fehler", "P-7", "Rechnungsnummer fehlt.", legal + " Nr. 4")
    if not inv.lines:
        add("fehler", "P-8", "Keine Rechnungspositionen – Menge und Art der Leistung nicht erkennbar.", legal + " Nr. 5")
    else:
        for ln in inv.lines:
            if not ln.name:
                add("fehler", "P-8b", f"Position {ln.line_id or '?'}: Bezeichnung der Leistung fehlt.", legal + " Nr. 5")
            if ln.quantity is None:
                add("warnung", "P-8c", f"Position {ln.line_id or '?'}: Menge fehlt.", legal + " Nr. 5")
    if not (inv.delivery_date or inv.period_start or inv.period_end):
        add("warnung", "P-9",
            "Kein Liefer-/Leistungsdatum und kein Leistungszeitraum angegeben. Zulässig ist das nur, wenn "
            "Leistungs- und Rechnungsdatum identisch sind und das aus der Rechnung hervorgeht (z. B. Hinweis "
            "\"Leistungsdatum entspricht Rechnungsdatum\").", legal + " Nr. 6")
    if not inv.taxes:
        add("fehler", "P-10", "Keine Aufschlüsselung nach Steuersätzen.", legal + " Nr. 7/8")
    if not inv.currency:
        add("warnung", "P-11", "Rechnungswährung fehlt.")

    # --- Steuerkategorien und Sonderfälle
    note_text = " ".join(inv.notes + inv.line_tax_texts).lower()
    for t in inv.taxes:
        if t.category == "AE":
            reason = (t.exemption_reason + " " + note_text).lower()
            if "steuerschuldnerschaft" not in reason and "reverse charge" not in reason:
                add("fehler", "RC-1",
                    "Reverse-Charge-Rechnung ohne den Pflichthinweis \"Steuerschuldnerschaft des Leistungsempfängers\".",
                    "§ 14a Abs. 5 UStG")
            else:
                add("info", "RC-2",
                    "Reverse Charge: SIE schulden die Umsatzsteuer und müssen sie selbst anmelden "
                    "(und können sie zugleich als Vorsteuer abziehen, sofern berechtigt).", "§ 13b UStG")
            if not inv.buyer.vat_id and inv.seller.address.country and inv.seller.address.country != "DE":
                add("warnung", "RC-3", "Ausländischer Lieferant mit Reverse Charge, aber Ihre USt-IdNr. fehlt auf der Rechnung.", "§ 14a Abs. 1 UStG")
        if t.category in {"E", "K", "G", "O"} and not (t.exemption_reason or t.exemption_code):
            add("fehler", "TX-1",
                f"Steuerkategorie {t.category} ohne Befreiungsgrund (BT-120/121).", "§ 14 Abs. 4 Nr. 8 UStG")
        if t.category == "K" and not inv.buyer.vat_id:
            add("fehler", "TX-2", "Innergemeinschaftliche Lieferung ohne USt-IdNr. des Empfängers.", "§ 14a Abs. 3 UStG")
        if t.category == "S" and t.rate is not None and t.rate not in (Decimal("19"), Decimal("7")) and \
                inv.seller.address.country in ("DE", ""):
            add("warnung", "TX-3", f"Ungewöhnlicher Steuersatz {t.rate} % bei deutschem Lieferanten (üblich: 19 % / 7 %).")
        if t.category == "E" and "19" in (t.exemption_reason or "") and "ustg" in (t.exemption_reason or "").lower():
            add("info", "KU-1", "Rechnung eines Kleinunternehmers (§ 19 UStG) – es ist keine Vorsteuer abziehbar.")

    # --- Rechnerische Prüfung
    t = inv.totals
    line_sum = sum((ln.net_amount or Decimal(0)) for ln in inv.lines)
    if t.line_total is not None and inv.lines and abs(line_sum - t.line_total) > TOL:
        add("fehler", "R-1", f"Summe der Positionen ({_m(line_sum)}) ≠ ausgewiesene Nettosumme ({_m(t.line_total)}).")

    for ln in inv.lines:
        if ln.quantity is not None and ln.unit_price is not None and ln.net_amount is not None \
                and not ln.has_line_allowance_or_charge:
            base = ln.price_base_qty or Decimal(1)
            if base == 0:
                continue
            expected = _r(ln.quantity * ln.unit_price / base)
            if abs(expected - ln.net_amount) > TOL:
                add("warnung", "R-2",
                    f"Position {ln.line_id}: Menge × Preis = {_m(expected)}, ausgewiesen {_m(ln.net_amount)}.")

    if t.line_total is not None and t.tax_basis_total is not None:
        expected_basis = t.line_total - (t.allowance_total or 0) + (t.charge_total or 0)
        if abs(expected_basis - t.tax_basis_total) > TOL:
            add("fehler", "R-3", f"Netto ± Zu-/Abschläge = {_m(expected_basis)}, ausgewiesen {_m(t.tax_basis_total)}.")

    for tb in inv.taxes:
        if tb.basis is not None and tb.rate is not None and tb.amount is not None:
            exp = _r(tb.basis * tb.rate / 100)
            if abs(exp - tb.amount) > TOL:
                add("fehler", "R-4", f"USt {tb.rate} % auf {_m(tb.basis)} ergibt {_m(exp)}, ausgewiesen {_m(tb.amount)}.")
    if inv.taxes and t.tax_total is not None:
        s = sum((tb.amount or Decimal(0)) for tb in inv.taxes)
        if abs(s - t.tax_total) > TOL:
            add("fehler", "R-5", f"Summe der Steuerbeträge ({_m(s)}) ≠ Gesamtsteuer ({_m(t.tax_total)}).")
    if inv.taxes and t.tax_basis_total is not None:
        s = sum((tb.basis or Decimal(0)) for tb in inv.taxes)
        if abs(s - t.tax_basis_total) > TOL:
            add("fehler", "R-6", f"Summe der Bemessungsgrundlagen ({_m(s)}) ≠ Nettobetrag ({_m(t.tax_basis_total)}).")
    if t.tax_basis_total is not None and t.grand_total is not None:
        exp = t.tax_basis_total + (t.tax_total or 0)
        if abs(exp - t.grand_total) > TOL:
            add("fehler", "R-7", f"Netto + USt = {_m(exp)}, ausgewiesener Bruttobetrag {_m(t.grand_total)}.")
    if t.grand_total is not None and t.payable is not None:
        exp = t.grand_total - (t.prepaid or 0) + (t.rounding or 0) + (t.third_party or 0)
        if abs(exp - t.payable) > TOL:
            add("fehler", "R-8", f"Brutto − Anzahlungen = {_m(exp)}, ausgewiesener Zahlbetrag {_m(t.payable)}.")
    if t.payable is None:
        add("fehler", "R-9", "Kein Zahlbetrag (BT-115) angegeben.")

    # --- Zahlung
    if inv.iban:
        if not iban_valid(inv.iban):
            add("fehler", "Z-1", f"IBAN {inv.iban} hat eine ungültige Prüfziffer bzw. Länge – NICHT überweisen, Lieferanten telefonisch kontaktieren.")
        elif inv.seller.address.country and inv.iban[:2].upper() != inv.seller.address.country.upper():
            add("warnung", "Z-2",
                f"IBAN-Land ({inv.iban[:2].upper()}) weicht vom Sitzland des Lieferanten ({inv.seller.address.country}) ab. "
                "Bei unbekannten Lieferanten vor Zahlung telefonisch verifizieren.")
    elif inv.payment_means_code in {"30", "31", "42", "58"} and not inv.is_credit_note:
        add("warnung", "Z-3", "Überweisung als Zahlungsart, aber keine IBAN angegeben.")
    if inv.due_date and inv.due_date < today and not inv.is_credit_note and (t.payable or 0) > 0:
        add("info", "Z-4", f"Fälligkeit {inv.due_date:%d.%m.%Y} ist bereits überschritten.")

    # --- Identifikationsnummern
    for who, party in (("Lieferanten", inv.seller), ("Empfängers", inv.buyer)):
        if party.vat_id:
            fmt = vat_id_format_ok(party.vat_id)
            de = de_vat_id_valid(party.vat_id)
            if fmt is False or de is False:
                add("warnung", "ID-1",
                    f"USt-IdNr. des {who} ({party.vat_id}) ist formal ungültig. Online beim BZSt bzw. per EU-VIES prüfen.")

    # --- Behörden / XRechnung
    if inv.is_xrechnung and not inv.buyer_reference:
        add("fehler", "X-1", "XRechnung ohne Käuferreferenz/Leitweg-ID (BT-10).", "XRechnung BR-DE-15")

    return f


def check_against_history(inv: Invoice, history: Iterable[dict]) -> list[Finding]:
    """Vergleicht mit früher geprüften Rechnungen (Duplikat, IBAN-Wechsel)."""
    f: list[Finding] = []
    seller_key = (inv.seller.vat_id or inv.seller.tax_number or inv.seller.name).upper()
    known_ibans: set[str] = set()
    for h in history:
        if h.get("hash") == getattr(inv, "_hash", None):
            continue  # dieselbe Datei ist kein Vergleichsmaßstab für sich selbst
        h_key = (h.get("seller_vat") or h.get("seller_tax") or h.get("seller_name") or "").upper()
        if h_key != seller_key:
            continue
        if h.get("number") == inv.number and not any(x.code == "H-1" for x in f):
            f.append(Finding("warnung", "H-1",
                             f"Rechnungsnummer {inv.number} dieses Lieferanten wurde bereits am "
                             f"{'.'.join(reversed(h.get('checked_at', '????-??-??')[:10].split('-')))} geprüft – mögliches Duplikat. Nicht doppelt bezahlen."))
        if h.get("iban"):
            known_ibans.add(h["iban"].replace(" ", "").upper())
    cur = inv.iban.replace(" ", "").upper()
    if cur and known_ibans and cur not in known_ibans:
        f.append(Finding("fehler", "H-2",
                         "ACHTUNG: Die IBAN dieses Lieferanten hat sich gegenüber früheren Rechnungen geändert "
                         f"(bisher: {', '.join(sorted(known_ibans))}). Geänderte Bankdaten sind das häufigste Muster "
                         "bei Rechnungsbetrug. Vor der Zahlung über eine BEKANNTE Telefonnummer beim Lieferanten "
                         "rückfragen – nicht über Kontaktdaten aus der Rechnung."))
    return f


def summarize(findings: list[Finding]) -> tuple[str, str]:
    errors = sum(1 for x in findings if x.severity == "fehler")
    warns = sum(1 for x in findings if x.severity == "warnung")
    if errors:
        return "rot", f"{errors} Fehler, {warns} Warnungen – Rechnung beim Lieferanten beanstanden, bevor Sie zahlen oder Vorsteuer ziehen."
    if warns:
        return "gelb", f"Keine harten Fehler, aber {warns} Hinweise zum Prüfen."
    return "gruen", "Alle Prüfungen bestanden."
