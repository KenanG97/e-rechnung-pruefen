"""Normalisiertes Datenmodell für E-Rechnungen (UBL und UN/CEFACT CII).

Alle Beträge sind Decimal, damit Rundungsprüfungen exakt sind.
Feldnamen orientieren sich an den Business Terms (BT-x) der EN 16931.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from decimal import Decimal
from typing import Optional


@dataclass
class Address:
    street: str = ""          # BT-35 / BT-50
    additional: str = ""      # BT-36 / BT-51
    city: str = ""            # BT-37 / BT-52
    postcode: str = ""        # BT-38 / BT-53
    country: str = ""         # BT-40 / BT-55

    def is_empty(self) -> bool:
        return not (self.street or self.city or self.postcode)

    def one_line(self) -> str:
        parts = [p for p in (self.street, self.additional) if p]
        loc = " ".join(p for p in (self.postcode, self.city) if p)
        if loc:
            parts.append(loc)
        if self.country:
            parts.append(self.country)
        return ", ".join(parts)


@dataclass
class Party:
    name: str = ""            # BT-27 / BT-44
    address: Address = field(default_factory=Address)
    vat_id: str = ""          # BT-31 / BT-48 (USt-IdNr.)
    tax_number: str = ""      # BT-32 (Steuernummer)
    electronic_address: str = ""  # BT-34 / BT-49
    contact_name: str = ""
    contact_phone: str = ""
    contact_email: str = ""


@dataclass
class Line:
    line_id: str = ""
    name: str = ""
    description: str = ""
    quantity: Optional[Decimal] = None
    unit: str = ""
    unit_price: Optional[Decimal] = None
    price_base_qty: Optional[Decimal] = None
    net_amount: Optional[Decimal] = None
    vat_category: str = ""
    vat_rate: Optional[Decimal] = None
    has_line_allowance_or_charge: bool = False


@dataclass
class TaxBreakdown:
    category: str = ""        # BT-118
    rate: Optional[Decimal] = None  # BT-119
    basis: Optional[Decimal] = None  # BT-116
    amount: Optional[Decimal] = None  # BT-117
    exemption_reason: str = ""      # BT-120
    exemption_code: str = ""        # BT-121


@dataclass
class Totals:
    line_total: Optional[Decimal] = None       # BT-106
    allowance_total: Optional[Decimal] = None  # BT-107
    charge_total: Optional[Decimal] = None     # BT-108
    tax_basis_total: Optional[Decimal] = None  # BT-109
    tax_total: Optional[Decimal] = None        # BT-110
    grand_total: Optional[Decimal] = None      # BT-112
    prepaid: Optional[Decimal] = None          # BT-113
    rounding: Optional[Decimal] = None         # BT-114
    payable: Optional[Decimal] = None          # BT-115
    third_party: Optional[Decimal] = None      # BT-DEX-002 (XRechnung-Extension: Drittforderungen)


@dataclass
class Invoice:
    source_name: str = ""
    syntax: str = ""            # "CII" oder "UBL"
    container: str = ""         # "XML" oder "PDF (ZUGFeRD/Factur-X)"
    guideline: str = ""         # BT-24 Spezifikationskennung
    number: str = ""            # BT-1
    type_code: str = ""         # BT-3
    issue_date: Optional[date] = None   # BT-2
    due_date: Optional[date] = None     # BT-9
    delivery_date: Optional[date] = None  # BT-72
    period_start: Optional[date] = None   # BT-73
    period_end: Optional[date] = None     # BT-74
    currency: str = ""          # BT-5
    buyer_reference: str = ""   # BT-10 (Leitweg-ID bei Behörden)
    order_reference: str = ""   # BT-13
    notes: list[str] = field(default_factory=list)
    seller: Party = field(default_factory=Party)
    buyer: Party = field(default_factory=Party)
    payment_means_code: str = ""   # BT-81
    iban: str = ""                 # BT-84
    bic: str = ""                  # BT-86
    payment_terms: str = ""        # BT-20
    lines: list[Line] = field(default_factory=list)
    line_tax_texts: list[str] = field(default_factory=list)  # Befreiungsgründe auf Positionsebene
    taxes: list[TaxBreakdown] = field(default_factory=list)
    totals: Totals = field(default_factory=Totals)

    @property
    def is_credit_note(self) -> bool:
        return self.type_code in {"381", "396", "532"}

    @property
    def is_xrechnung(self) -> bool:
        return "xrechnung" in self.guideline.lower()

    def to_dict(self) -> dict:
        return asdict(self)


TYPE_CODES = {
    "380": "Rechnung",
    "381": "Gutschrift (Credit Note)",
    "384": "Korrigierte Rechnung",
    "389": "Gutschrift im Gutschriftverfahren (Self-billing)",
    "326": "Teilrechnung",
    "875": "Abschlagsrechnung",
    "876": "Teilschlussrechnung",
    "877": "Schlussrechnung",
    "751": "Rechnungsinformation (keine Rechnung i. S. d. UStG)",
}

VAT_CATEGORIES = {
    "S": "Normalsatz / ermäßigter Satz",
    "Z": "Nullsatz",
    "E": "Steuerbefreit",
    "AE": "Reverse Charge (Steuerschuldnerschaft des Leistungsempfängers)",
    "K": "Innergemeinschaftliche Lieferung",
    "G": "Ausfuhrlieferung (Drittland)",
    "O": "Nicht steuerbar",
    "L": "IGIC (Kanaren)",
    "M": "IPSI (Ceuta/Melilla)",
}

PAYMENT_MEANS = {
    "10": "Bar",
    "20": "Scheck",
    "30": "Überweisung",
    "31": "Überweisung",
    "42": "Zahlung auf Bankkonto",
    "48": "Karte",
    "49": "Lastschrift",
    "57": "Dauerauftrag",
    "58": "SEPA-Überweisung",
    "59": "SEPA-Lastschrift",
    "68": "Online-Zahlung",
    "97": "Verrechnung",
    "ZZZ": "Sonstige",
}

UNIT_CODES = {
    "C62": "Stk", "H87": "Stk", "XPP": "Stk", "EA": "Stk", "HUR": "Std", "MIN": "Min",
    "DAY": "Tag", "WEE": "Woche", "MON": "Monat", "ANN": "Jahr", "KGM": "kg",
    "GRM": "g", "TNE": "t", "MTR": "m", "KMT": "km", "MTK": "m²", "MTQ": "m³",
    "LTR": "l", "KWH": "kWh", "LS": "pauschal", "SET": "Set", "XBO": "Flasche",
    "XBX": "Karton", "P1": "%", "E48": "Leistungseinheit",
}
