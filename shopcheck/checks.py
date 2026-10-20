"""Prüfregeln.

Grundpreis – § 4 PAngV (Deutschland, Fassung ab 28.05.2022): Wer Verbrauchern Waren in
Fertigpackungen, offenen Packungen oder als Verkaufseinheit ohne Umhüllung nach Gewicht,
Volumen, Länge oder Fläche anbietet, muss neben dem Gesamtpreis den Grundpreis angeben –
bezogen auf 1 kg, 1 l, 1 m, 1 m² oder 1 m³. Die frühere 100-g/100-ml-Option für Fertigpackungen
ist entfallen. Kein Grundpreis nötig u. a., wenn er mit dem Gesamtpreis identisch ist oder bei
Waren unter 10 g bzw. 10 ml Nenngewicht/-volumen (§ 5 PAngV). Österreich regelt die Grundpreis-
auszeichnung im Preisauszeichnungsgesetz; Details können abweichen.

GPSR – Art. 19 Verordnung (EU) 2023/988 (seit 13.12.2024): Fernabsatzangebote müssen Name,
Postanschrift und elektronische Adresse des Herstellers enthalten; sitzt dieser außerhalb der EU,
zusätzlich die der verantwortlichen Person in der EU; ferner Angaben zur Identifizierung des
Produkts (inkl. Abbildung) und Warn-/Sicherheitshinweise.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from kugrenze.bankcsv import parse_amount

from .products import Product

D = Decimal
CENT = D("0.01")

UNITS = {  # Einheit -> (Basiseinheit, Faktor zur Basiseinheit)
    "mg": ("kg", D("0.000001")), "g": ("kg", D("0.001")), "gr": ("kg", D("0.001")), "gramm": ("kg", D("0.001")),
    "kg": ("kg", D(1)), "kilo": ("kg", D(1)), "kilogramm": ("kg", D(1)),
    "ml": ("l", D("0.001")), "cl": ("l", D("0.01")), "dl": ("l", D("0.1")), "l": ("l", D(1)), "ltr": ("l", D(1)),
    "liter": ("l", D(1)), "litre": ("l", D(1)),
    "mm": ("m", D("0.001")), "cm": ("m", D("0.01")), "m": ("m", D(1)), "meter": ("m", D(1)), "lfm": ("m", D(1)),
    "m²": ("m²", D(1)), "m2": ("m²", D(1)), "qm": ("m²", D(1)), "m³": ("m³", D(1)), "m3": ("m³", D(1)),
}
_UNIT_RE = r"(mg|kg|kilogramm|kilo|gramm|gr|g|ml|cl|dl|ltr|liter|litre|l|mm|cm|lfm|meter|m²|m2|qm|m³|m3|m)"
_NUM = r"(\d+(?:[.,]\d+)?)"
_MASSVOL_RE = r"(mg|kg|kilogramm|kilo|gramm|gr|g|ml|cl|dl|ltr|liter|litre|l)"
MULTI = re.compile(rf"(\d+)\s*[x×]\s*{_NUM}\s*{_MASSVOL_RE}(?![a-zäöü0-9])", re.I)
SINGLE = re.compile(rf"(?<![\d.,]){_NUM}\s*{_UNIT_RE}(?![a-zäöü0-9])", re.I)
LABELLED = re.compile(rf"(inhalt|füllmenge|fuellmenge|nettofüllmenge|nettogewicht|nettoinhalt|net weight|net wt|nennfüllmenge|menge)\s*[:\-]?\s*"
                      rf"(?:(\d+)\s*[x×]\s*)?{_NUM}\s*{_UNIT_RE}(?![a-zäöü0-9])", re.I)
LENGTH_CONTEXT = re.compile(r"meterware|\bpro meter\b|\bje meter\b|rolle|spule|band\b|kordel|garn|kabel|schlauch|stoff|bordüre|"
                            r"folie|tapete|draht|seil|kette\b|litze|vlies|fliese|laminat|parkett|teppich|kunstrasen", re.I)
DECO_COSMETICS = re.compile(r"lippenstift|lipgloss|nagellack|make-?up|mascara|lidschatten|foundation|rouge|puder|concealer|eyeliner|"
                            r"kajal|highlighter|bronzer|parfum|eau de", re.I)
EXISTING_UP = re.compile(rf"(\d+(?:[.,]\d{{2}}))\s*(?:€|eur)?\s*(?:/|pro|je|per)\s*(1\s*|100\s*|1000\s*)?{_UNIT_RE}\b", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
URL = re.compile(r"\b(https?://|www\.)[\w.-]+\.[a-z]{2,}|\b[\w-]{2,}\.(at|de|ch|eu|com|net|org|es|it|fr|nl|be|pl|cz|dk|se|shop|store)\b", re.I)
MF_LABEL = re.compile(r"(hersteller|manufacturer|produced by|hergestellt von|inverkehrbringer)\s*[:\-]\s*\S", re.I)
POSTAL = re.compile(r"\b(\d{4,5})\s+[A-ZÄÖÜ][\wäöüß.-]+|\b[A-ZÄÖÜ][\wäöüß-]*(straße|strasse|str\.|gasse|weg|platz|allee|ring|road|street|st\.)\s*\d+", re.I)
NON_EU = re.compile(r"\b(china|p\.?r\.?c\.?|shenzhen|guangzhou|shanghai|beijing|hong ?kong|taiwan|usa|u\.s\.a\.|united states|"
                    r"united kingdom|great britain|\buk\b|england|türkei|turkey|indien|india|vietnam|bangladesh|pakistan|"
                    r"schweiz|switzerland|norway|norwegen|japan|korea)\b", re.I)
EU_RESPONSIBLE = re.compile(r"verantwortliche person|responsible person|eu-?bevollmächtigt|eu-?vertreter|eu representative|"
                            r"importeur|importer|inverkehrbringer|eu-?verantwortlich", re.I)
RISK = re.compile(r"spielzeug|kinder|baby|kleinkind|elektr|akku|batterie|ladegerät|netzteil|kerze|duftöl|ätherisch|kosmetik|"
                  r"creme|seife|reiniger|chemi|magnet|laser|messer|klinge|heiz|wärm|glas|e-?bike|helm|toy|battery", re.I)
WARNING_WORDS = re.compile(r"warn|sicherheit|achtung|vorsicht|safety|caution|nicht geeignet für|außer reichweite|ausser reichweite|"
                           r"erstickungsgefahr|nur unter aufsicht", re.I)


@dataclass
class Finding:
    severity: str
    code: str
    message: str
    legal: str = ""


def _num(s: str) -> D:
    return D(s.replace(",", "."))


def parse_quantity(text: str) -> Optional[tuple[D, str, str]]:
    """Füllmenge aus Text -> (Menge in Basiseinheit, Basiseinheit, Fundstelle)."""
    if not text:
        return None
    m = LABELLED.search(text)
    if m:
        cnt = int(m.group(2)) if m.group(2) else 1
        val, unit = _num(m.group(3)), m.group(4).lower()
        base, f = UNITS[unit]
        return val * cnt * f, base, m.group(0).strip()
    m = MULTI.search(text)
    if m:
        cnt, val, unit = int(m.group(1)), _num(m.group(2)), m.group(3).lower()
        base, f = UNITS[unit]
        return val * cnt * f, base, m.group(0).strip()
    # Abmessungen wie „30 x 40 cm“ oder „Ø 12 cm“ sind keine Füllmenge
    for m in SINGLE.finditer(text):
        unit = m.group(2).lower()
        base, f = UNITS[unit]
        before = text[max(0, m.start() - 4):m.start()]
        if re.search(r"[x×Ø]\s*$", before) or (base == "m" and re.match(r"\s*[x×]", text[m.end():m.end() + 3])):
            continue
        return _num(m.group(1)) * f, base, m.group(0).strip()
    return None


def unit_price(price: D, qty: D, base: str) -> D:
    return (price / qty).quantize(CENT, rounding=ROUND_HALF_UP)


def fmt_eur(x: D) -> str:
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def fmt_qty(q: D, base: str) -> str:
    small = {"kg": ("g", 1000), "l": ("ml", 1000), "m": ("cm", 100)}
    if base in small and q < 1:
        u, f = small[base]
        v = (q * f).normalize()
        return f"{v:f}".replace(".", ",") + f" {u}"
    return f"{q.normalize():f}".replace(".", ",") + f" {base}"


def _shopify_unit_measure(p: Product) -> Optional[tuple[str, str, str, str]]:
    low = {k.lower(): v.strip() for k, v in p.raw.items()}
    tm, tu = low.get("unit price total measure", ""), low.get("unit price total measure unit", "")
    bm, bu = low.get("unit price base measure", ""), low.get("unit price base measure unit", "")
    if tm and tu:
        return tm, tu, bm, bu
    return None


def check_product(p: Product) -> tuple[list[Finding], dict]:
    f: list[Finding] = []
    info: dict = {}
    pangv = "§ 4 PAngV"
    name_variant = f"{p.title} {p.variant}".strip()
    q = parse_quantity(name_variant) or parse_quantity(p.description if LABELLED.search(p.description or "") else "")
    if q and q[1] == "m" and not LENGTH_CONTEXT.search(f"{p.title} {p.description[:300]}"):
        info["quantity_note"] = f"„{q[2]}“ als Maß erkannt, nicht als Verkaufsmenge"
        q = None
    if q:
        qty, base, found = q
        info.update(quantity=str(qty), base=base, quantity_text=found)
        small = (base in ("kg", "l") and qty < D("0.010"))
        identical = qty == 1
        if small:
            f.append(Finding("info", "GP-0", f"Füllmenge {found} unter 10 g/ml – kein Grundpreis erforderlich.", "§ 5 PAngV"))
        elif identical:
            f.append(Finding("info", "GP-0", f"Füllmenge genau 1 {base} – Grundpreis entspricht dem Gesamtpreis.", "§ 5 PAngV"))
        elif p.price is None or p.price <= 0:
            f.append(Finding("warnung", "GP-5", "Füllmenge erkannt, aber kein Preis – Grundpreis nicht berechenbar."))
        else:
            up = unit_price(p.price, qty, base)
            info["unit_price"] = str(up)
            info["unit_price_text"] = f"{fmt_eur(up)} / 1 {base}"
            shop = _shopify_unit_measure(p)
            existing = EXISTING_UP.search(" ".join([p.unit_price_text, p.title, p.description]))
            if shop:
                tm, tu, bm, bu = shop
                sq = parse_quantity(f"{tm} {tu}")
                if bu and bu.lower() not in ("kg", "l", "m", "m2", "m²", "m3", "m³") or (bm and parse_amount(bm) != 1):
                    f.append(Finding("fehler", "GP-3", f"Shopify-Grundpreis bezieht sich auf {bm} {bu}. Seit 2022 muss er sich auf "
                                     "1 kg, 1 l, 1 m, 1 m² oder 1 m³ beziehen.", pangv))
                elif sq and abs(sq[0] - qty) > qty * D("0.001"):
                    f.append(Finding("fehler", "GP-4", f"Shopify-Grundpreis rechnet mit {tm} {tu}, im Titel steht {found}.", pangv))
            elif existing:
                val = _num(existing.group(1))
                per = (existing.group(2) or "1").strip()
                unit = existing.group(3).lower()
                if per in ("100", "1000") or unit in ("g", "ml", "cl"):
                    f.append(Finding("fehler", "GP-3", f"Grundpreis „{existing.group(0)}“ bezieht sich nicht auf 1 kg bzw. 1 l. "
                                     "Die 100-g-Angabe ist für Fertigpackungen seit 28.05.2022 nicht mehr zulässig.", pangv))
                elif abs(val - up) > CENT:
                    f.append(Finding("fehler", "GP-2", f"Angegebener Grundpreis {fmt_eur(val)} weicht vom berechneten "
                                     f"{fmt_eur(up)} / 1 {base} ab ({fmt_eur(p.price)} für {found}).", pangv))
            else:
                f.append(Finding("fehler", "GP-1", f"Grundpreis fehlt: {fmt_eur(p.price)} für {found} = {fmt_eur(up)} / 1 {base}.", pangv))
            if DECO_COSMETICS.search(p.title) and any(x.code.startswith("GP-") and x.severity == "fehler" for x in f):
                f.append(Finding("info", "GP-6", "Dekorative Kosmetik/Parfum kann von der Grundpreispflicht ausgenommen sein – im Einzelfall prüfen.", "§ 5 PAngV"))

    # --- GPSR
    gpsr = "Art. 19 GPSR (VO (EU) 2023/988)"
    mtext = f"{p.manufacturer_text} {p.description}"
    if not (p.vendor or p.manufacturer_text or MF_LABEL.search(p.description or "")):
        f.append(Finding("fehler", "PS-1", "Kein Hersteller bzw. keine Marke angegeben.", gpsr + " lit. a"))
    has_contact = bool(EMAIL.search(mtext) or URL.search(mtext))
    has_postal = bool(POSTAL.search(mtext))
    if not (has_contact and has_postal):
        missing = " und ".join(x for x, ok in (("Postanschrift", has_postal), ("E-Mail/Website", has_contact)) if not ok)
        f.append(Finding("fehler", "PS-2", f"{missing} des Herstellers nicht in den Produktdaten gefunden. Falls Ihr Shop diese "
                         "Angaben über eine andere Quelle (z. B. Metafeld, Theme-Block) anzeigt, ist das in Ordnung – sonst ergänzen.",
                         gpsr + " lit. a"))
    if NON_EU.search(mtext) and not EU_RESPONSIBLE.search(mtext):
        f.append(Finding("fehler", "PS-3", "Hinweis auf einen Hersteller außerhalb der EU, aber keine verantwortliche Person in der EU angegeben.",
                         gpsr + " lit. b, Art. 4 VO (EU) 2019/1020"))
    if not p.image:
        f.append(Finding("warnung", "PS-4", "Kein Produktbild in den Daten.", gpsr + " lit. c"))
    if RISK.search(f"{p.title} {p.category} {p.description[:500]}") and not WARNING_WORDS.search(p.description):
        f.append(Finding("warnung", "PS-5", "Produktart mit typischem Sicherheitsbezug, aber keine Warn- oder Sicherheitshinweise in der Beschreibung.",
                         gpsr + " lit. d"))
    return f, info
