"""Parser für XRechnung/ZUGFeRD/Factur-X in beiden Syntaxen (UBL 2.1 und UN/CEFACT CII D16B).

Der Parser ist bewusst tolerant: Er liest so viel wie möglich und überlässt das Urteil
über Vollständigkeit dem Prüfmodul (checks.py). XML wird mit lxml im sicheren Modus
geparst (keine externen Entitäten, kein Netzwerkzugriff) – wichtig, weil Dateien von
Fremden hochgeladen werden. Ohne lxml (z. B. im Browser via Pyodide) wird die Standardbibliothek
genutzt; Dokumente mit DOCTYPE werden in beiden Fällen abgelehnt (kein XXE, keine Entity-Bomben).
"""
from __future__ import annotations

import io
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

try:  # schnell & gehärtet, wenn verfügbar
    from lxml import etree as _lx
except ImportError:  # Browser/Pyodide
    _lx = None
import xml.etree.ElementTree as _ET

from .model import Address, Invoice, Line, Party, TaxBreakdown, Totals

NS = {
    # CII
    "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
    "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
    "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
    "qdt": "urn:un:unece:uncefact:data:standard:QualifiedDataType:100",
    # UBL
    "inv": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cn": "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}

MAX_FILE_BYTES = 15 * 1024 * 1024  # Schutz gegen übergroße Uploads

KNOWN_ATTACHMENT_NAMES = (
    "factur-x.xml", "zugferd-invoice.xml", "xrechnung.xml", "zugferd_invoice.xml",
)


class ParseError(Exception):
    """Datei ist keine lesbare E-Rechnung."""


# ---------------------------------------------------------------- Hilfsfunktionen

def _xml_root(data: bytes):
    head = data[:4096].lstrip(b"\xef\xbb\xbf \t\r\n")
    if b"<!DOCTYPE" in data[:65536] or b"<!ENTITY" in data[:65536]:
        raise ParseError("Keine gültige E-Rechnung: XML mit DOCTYPE/Entitäten wird aus Sicherheitsgründen abgelehnt.")
    if not head.startswith(b"<"):
        raise ParseError("Keine gültige XML-Datei.")
    try:
        if _lx is not None:
            parser = _lx.XMLParser(resolve_entities=False, no_network=True, dtd_validation=False,
                                   load_dtd=False, huge_tree=False, remove_comments=True)
            return _lx.fromstring(data, parser)
        return _ET.fromstring(data)
    except Exception as exc:
        raise ParseError(f"Keine gültige XML-Datei: {exc}") from exc


def _qname(el) -> tuple[str, str]:
    tag = el.tag if isinstance(el.tag, str) else ""
    if tag.startswith("{"):
        ns, local = tag[1:].split("}", 1)
        return ns, local
    return "", tag


def _txt(node, path: str) -> str:
    if node is None:
        return ""
    found = node.find(path, NS)
    if found is None or found.text is None:
        return ""
    return " ".join(found.text.split())


def _dec(node, path: str) -> Optional[Decimal]:
    raw = _txt(node, path)
    if not raw:
        return None
    try:
        return Decimal(raw.replace(",", "."))
    except InvalidOperation:
        return None


def _date_cii(node, path: str) -> Optional[date]:
    raw = _txt(node, path)
    return _parse_date(raw)


def _parse_date(raw: str) -> Optional[date]:
    raw = (raw or "").strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y%m", "%d.%m.%Y"):
        try:
            return datetime.strptime(raw[:10] if "-" in raw else raw, fmt).date()
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------- PDF (ZUGFeRD)

def extract_xml_from_pdf(data: bytes) -> tuple[bytes, str]:
    """Holt die eingebettete Rechnungs-XML aus einem ZUGFeRD-/Factur-X-PDF."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise ParseError("pypdf ist nicht installiert.") from exc
    try:
        reader = PdfReader(io.BytesIO(data))
        attachments = reader.attachments  # {name: [bytes, ...]}
    except Exception as exc:  # beschädigte PDFs
        raise ParseError(f"PDF konnte nicht gelesen werden: {exc}") from exc

    if not attachments:
        raise ParseError(
            "Dieses PDF enthält keine eingebetteten Rechnungsdaten. Es ist eine "
            "gewöhnliche PDF-Rechnung und damit keine E-Rechnung im Sinne von § 14 UStG."
        )
    by_lower = {name.lower(): name for name in attachments}
    for wanted in KNOWN_ATTACHMENT_NAMES:
        if wanted in by_lower:
            name = by_lower[wanted]
            return attachments[name][0], name
    for name, contents in attachments.items():
        if name.lower().endswith(".xml"):
            return contents[0], name
    raise ParseError(
        "Das PDF hat Anhänge, aber keine Rechnungs-XML (gefunden: "
        + ", ".join(attachments) + ")."
    )


# ---------------------------------------------------------------- Einstieg

def parse_bytes(data: bytes, source_name: str = "") -> Invoice:
    if len(data) > MAX_FILE_BYTES:
        raise ParseError("Datei ist größer als 15 MB.")
    container = "XML"
    if data[:5] == b"%PDF-":
        data, att = extract_xml_from_pdf(data)
        container = f"PDF (ZUGFeRD/Factur-X, Anhang {att})"
    root = _xml_root(data)
    nsuri, tag = _qname(root)
    if tag == "CrossIndustryInvoice" and nsuri == NS["rsm"]:
        inv = _parse_cii(root)
    elif tag == "Invoice" and nsuri == NS["inv"]:
        inv = _parse_ubl(root, credit=False)
    elif tag == "CreditNote" and nsuri == NS["cn"]:
        inv = _parse_ubl(root, credit=True)
    elif tag == "CrossIndustryDocument":
        raise ParseError("ZUGFeRD 1.0 wird nicht unterstützt (seit 2025 keine zulässige E-Rechnung mehr).")
    else:
        raise ParseError(f"Unbekanntes Format: Wurzelelement <{tag}>.")
    inv.source_name = source_name
    inv.container = container
    return inv


# ---------------------------------------------------------------- CII

def _cii_party(node) -> Party:
    p = Party()
    if node is None:
        return p
    p.name = _txt(node, "ram:Name")
    a = node.find("ram:PostalTradeAddress", NS)
    p.address = Address(
        street=_txt(a, "ram:LineOne"),
        additional=" ".join(x for x in (_txt(a, "ram:LineTwo"), _txt(a, "ram:LineThree")) if x),
        city=_txt(a, "ram:CityName"),
        postcode=_txt(a, "ram:PostcodeCode"),
        country=_txt(a, "ram:CountryID"),
    )
    for reg in node.findall("ram:SpecifiedTaxRegistration", NS):
        idn = reg.find("ram:ID", NS)
        if idn is None or not idn.text:
            continue
        scheme = idn.get("schemeID", "")
        if scheme == "VA":
            p.vat_id = idn.text.strip()
        elif scheme == "FC":
            p.tax_number = idn.text.strip()
    p.electronic_address = _txt(node, "ram:URIUniversalCommunication/ram:URIID")
    c = node.find("ram:DefinedTradeContact", NS)
    p.contact_name = _txt(c, "ram:PersonName") or _txt(c, "ram:DepartmentName")
    p.contact_phone = _txt(c, "ram:TelephoneUniversalCommunication/ram:CompleteNumber")
    p.contact_email = _txt(c, "ram:EmailURIUniversalCommunication/ram:URIID")
    return p


def _parse_cii(root) -> Invoice:
    inv = Invoice(syntax="CII")
    inv.guideline = _txt(root, "rsm:ExchangedDocumentContext/ram:GuidelineSpecifiedDocumentContextParameter/ram:ID")
    doc = root.find("rsm:ExchangedDocument", NS)
    inv.number = _txt(doc, "ram:ID")
    inv.type_code = _txt(doc, "ram:TypeCode")
    inv.issue_date = _date_cii(doc, "ram:IssueDateTime/udt:DateTimeString")
    inv.notes = [" ".join(n.text.split()) for n in root.findall(
        "rsm:ExchangedDocument/ram:IncludedNote/ram:Content", NS) if n.text]

    tx = root.find("rsm:SupplyChainTradeTransaction", NS)
    agr = tx.find("ram:ApplicableHeaderTradeAgreement", NS) if tx is not None else None
    dlv = tx.find("ram:ApplicableHeaderTradeDelivery", NS) if tx is not None else None
    stl = tx.find("ram:ApplicableHeaderTradeSettlement", NS) if tx is not None else None

    inv.buyer_reference = _txt(agr, "ram:BuyerReference")
    inv.order_reference = _txt(agr, "ram:BuyerOrderReferencedDocument/ram:IssuerAssignedID")
    inv.seller = _cii_party(agr.find("ram:SellerTradeParty", NS) if agr is not None else None)
    inv.buyer = _cii_party(agr.find("ram:BuyerTradeParty", NS) if agr is not None else None)
    inv.delivery_date = _date_cii(dlv, "ram:ActualDeliverySupplyChainEvent/ram:OccurrenceDateTime/udt:DateTimeString")

    if stl is not None:
        inv.currency = _txt(stl, "ram:InvoiceCurrencyCode")
        pm = stl.find("ram:SpecifiedTradeSettlementPaymentMeans", NS)
        inv.payment_means_code = _txt(pm, "ram:TypeCode")
        inv.iban = _txt(pm, "ram:PayeePartyCreditorFinancialAccount/ram:IBANID") or \
            _txt(pm, "ram:PayerPartyDebtorFinancialAccount/ram:IBANID")
        inv.bic = _txt(pm, "ram:PayeeSpecifiedCreditorFinancialInstitution/ram:BICID")
        inv.period_start = _date_cii(stl, "ram:BillingSpecifiedPeriod/ram:StartDateTime/udt:DateTimeString")
        inv.period_end = _date_cii(stl, "ram:BillingSpecifiedPeriod/ram:EndDateTime/udt:DateTimeString")
        terms = stl.find("ram:SpecifiedTradePaymentTerms", NS)
        inv.payment_terms = _txt(terms, "ram:Description")
        inv.due_date = _date_cii(terms, "ram:DueDateDateTime/udt:DateTimeString")
        for t in stl.findall("ram:ApplicableTradeTax", NS):
            inv.taxes.append(TaxBreakdown(
                category=_txt(t, "ram:CategoryCode"),
                rate=_dec(t, "ram:RateApplicablePercent"),
                basis=_dec(t, "ram:BasisAmount"),
                amount=_dec(t, "ram:CalculatedAmount"),
                exemption_reason=_txt(t, "ram:ExemptionReason"),
                exemption_code=_txt(t, "ram:ExemptionReasonCode"),
            ))
        s = stl.find("ram:SpecifiedTradeSettlementHeaderMonetarySummation", NS)
        tax_total = None
        if s is not None:
            # TaxTotalAmount kann zweimal vorkommen (Rechnungs- und Buchungswährung)
            for tt in s.findall("ram:TaxTotalAmount", NS):
                cur = tt.get("currencyID", "")
                if tt.text and (not cur or cur == inv.currency or tax_total is None):
                    tax_total = Decimal(tt.text.strip())
        inv.totals = Totals(
            line_total=_dec(s, "ram:LineTotalAmount"),
            allowance_total=_dec(s, "ram:AllowanceTotalAmount"),
            charge_total=_dec(s, "ram:ChargeTotalAmount"),
            tax_basis_total=_dec(s, "ram:TaxBasisTotalAmount"),
            tax_total=tax_total,
            grand_total=_dec(s, "ram:GrandTotalAmount"),
            prepaid=_dec(s, "ram:TotalPrepaidAmount"),
            rounding=_dec(s, "ram:RoundingAmount"),
            payable=_dec(s, "ram:DuePayableAmount"),
        )

    inv.line_tax_texts = [" ".join(e.text.split()) for e in root.iter(
        "{%s}ExemptionReason" % NS["ram"]) if e.text]
    for li in (tx.findall("ram:IncludedSupplyChainTradeLineItem", NS) if tx is not None else []):
        price = li.find("ram:SpecifiedLineTradeAgreement/ram:NetPriceProductTradePrice", NS)
        qty_el = li.find("ram:SpecifiedLineTradeDelivery/ram:BilledQuantity", NS)
        lstl = li.find("ram:SpecifiedLineTradeSettlement", NS)
        inv.lines.append(Line(
            line_id=_txt(li, "ram:AssociatedDocumentLineDocument/ram:LineID"),
            name=_txt(li, "ram:SpecifiedTradeProduct/ram:Name"),
            description=_txt(li, "ram:SpecifiedTradeProduct/ram:Description"),
            quantity=Decimal(qty_el.text.strip()) if qty_el is not None and qty_el.text else None,
            unit=qty_el.get("unitCode", "") if qty_el is not None else "",
            unit_price=_dec(price, "ram:ChargeAmount"),
            price_base_qty=_dec(price, "ram:BasisQuantity"),
            net_amount=_dec(lstl, "ram:SpecifiedTradeSettlementLineMonetarySummation/ram:LineTotalAmount"),
            vat_category=_txt(lstl, "ram:ApplicableTradeTax/ram:CategoryCode"),
            vat_rate=_dec(lstl, "ram:ApplicableTradeTax/ram:RateApplicablePercent"),
            has_line_allowance_or_charge=lstl is not None and lstl.find(
                "ram:SpecifiedTradeAllowanceCharge", NS) is not None,
        ))
    return inv


# ---------------------------------------------------------------- UBL

def _ubl_party(node) -> Party:
    p = Party()
    if node is None:
        return p
    p.name = _txt(node, "cac:PartyLegalEntity/cbc:RegistrationName") or _txt(node, "cac:PartyName/cbc:Name")
    a = node.find("cac:PostalAddress", NS)
    p.address = Address(
        street=_txt(a, "cbc:StreetName"),
        additional=" ".join(x for x in (_txt(a, "cbc:AdditionalStreetName"),
                                        _txt(a, "cac:AddressLine/cbc:Line")) if x),
        city=_txt(a, "cbc:CityName"),
        postcode=_txt(a, "cbc:PostalZone"),
        country=_txt(a, "cac:Country/cbc:IdentificationCode"),
    )
    for pts in node.findall("cac:PartyTaxScheme", NS):
        cid = _txt(pts, "cbc:CompanyID")
        scheme = _txt(pts, "cac:TaxScheme/cbc:ID").upper()
        if not cid:
            continue
        if scheme == "VAT":
            p.vat_id = cid
        else:
            p.tax_number = cid
    p.electronic_address = _txt(node, "cbc:EndpointID")
    c = node.find("cac:Contact", NS)
    p.contact_name = _txt(c, "cbc:Name")
    p.contact_phone = _txt(c, "cbc:Telephone")
    p.contact_email = _txt(c, "cbc:ElectronicMail")
    return p


def _parse_ubl(root, credit: bool) -> Invoice:
    inv = Invoice(syntax="UBL")
    inv.guideline = _txt(root, "cbc:CustomizationID")
    inv.number = _txt(root, "cbc:ID")
    inv.type_code = _txt(root, "cbc:CreditNoteTypeCode" if credit else "cbc:InvoiceTypeCode")
    inv.issue_date = _parse_date(_txt(root, "cbc:IssueDate"))
    inv.due_date = _parse_date(_txt(root, "cbc:DueDate")) or \
        _parse_date(_txt(root, "cac:PaymentMeans/cbc:PaymentDueDate"))
    inv.currency = _txt(root, "cbc:DocumentCurrencyCode")
    inv.buyer_reference = _txt(root, "cbc:BuyerReference")
    inv.order_reference = _txt(root, "cac:OrderReference/cbc:ID")
    inv.notes = [re.sub(r"^#[A-Z]{3}#", "", " ".join(n.text.split())) for n in root.findall("cbc:Note", NS) if n.text]
    inv.seller = _ubl_party(root.find("cac:AccountingSupplierParty/cac:Party", NS))
    inv.buyer = _ubl_party(root.find("cac:AccountingCustomerParty/cac:Party", NS))
    inv.delivery_date = _parse_date(_txt(root, "cac:Delivery/cbc:ActualDeliveryDate"))
    inv.period_start = _parse_date(_txt(root, "cac:InvoicePeriod/cbc:StartDate"))
    inv.period_end = _parse_date(_txt(root, "cac:InvoicePeriod/cbc:EndDate"))

    pm = root.find("cac:PaymentMeans", NS)
    inv.payment_means_code = _txt(pm, "cbc:PaymentMeansCode")
    inv.iban = _txt(pm, "cac:PayeeFinancialAccount/cbc:ID") or \
        _txt(pm, "cac:PaymentMandate/cac:PayerFinancialAccount/cbc:ID")
    inv.bic = _txt(pm, "cac:PayeeFinancialAccount/cac:FinancialInstitutionBranch/cbc:ID")
    inv.payment_terms = _txt(root, "cac:PaymentTerms/cbc:Note")

    tax_total = None
    for tt in root.findall("cac:TaxTotal", NS):
        amt = tt.find("cbc:TaxAmount", NS)
        if amt is not None and amt.text and (amt.get("currencyID", "") in ("", inv.currency) or tax_total is None):
            tax_total = Decimal(amt.text.strip())
        for sub in tt.findall("cac:TaxSubtotal", NS):
            cat = sub.find("cac:TaxCategory", NS)
            inv.taxes.append(TaxBreakdown(
                category=_txt(cat, "cbc:ID"),
                rate=_dec(cat, "cbc:Percent"),
                basis=_dec(sub, "cbc:TaxableAmount"),
                amount=_dec(sub, "cbc:TaxAmount"),
                exemption_reason=_txt(cat, "cbc:TaxExemptionReason"),
                exemption_code=_txt(cat, "cbc:TaxExemptionReasonCode"),
            ))

    lmt = root.find("cac:LegalMonetaryTotal", NS)
    inv.totals = Totals(
        line_total=_dec(lmt, "cbc:LineExtensionAmount"),
        allowance_total=_dec(lmt, "cbc:AllowanceTotalAmount"),
        charge_total=_dec(lmt, "cbc:ChargeTotalAmount"),
        tax_basis_total=_dec(lmt, "cbc:TaxExclusiveAmount"),
        tax_total=tax_total,
        grand_total=_dec(lmt, "cbc:TaxInclusiveAmount"),
        prepaid=_dec(lmt, "cbc:PrepaidAmount"),
        rounding=_dec(lmt, "cbc:PayableRoundingAmount"),
        payable=_dec(lmt, "cbc:PayableAmount"),
    )
    tp = [_dec(pp, "cbc:PaidAmount") for pp in root.findall("cac:PrepaidPayment", NS)]
    tp = [x for x in tp if x is not None]
    if tp:
        inv.totals.third_party = sum(tp)
    inv.line_tax_texts = [" ".join(e.text.split()) for e in root.iter(
        "{%s}TaxExemptionReason" % NS["cbc"]) if e.text]

    line_tag, qty_tag = ("cac:CreditNoteLine", "cbc:CreditedQuantity") if credit else \
        ("cac:InvoiceLine", "cbc:InvoicedQuantity")
    for li in root.findall(line_tag, NS):
        q = li.find(qty_tag, NS)
        inv.lines.append(Line(
            line_id=_txt(li, "cbc:ID"),
            name=_txt(li, "cac:Item/cbc:Name"),
            description=_txt(li, "cac:Item/cbc:Description"),
            quantity=Decimal(q.text.strip()) if q is not None and q.text else None,
            unit=q.get("unitCode", "") if q is not None else "",
            unit_price=_dec(li, "cac:Price/cbc:PriceAmount"),
            price_base_qty=_dec(li, "cac:Price/cbc:BaseQuantity"),
            net_amount=_dec(li, "cbc:LineExtensionAmount"),
            vat_category=_txt(li, "cac:Item/cac:ClassifiedTaxCategory/cbc:ID"),
            vat_rate=_dec(li, "cac:Item/cac:ClassifiedTaxCategory/cbc:Percent"),
            has_line_allowance_or_charge=li.find("cac:AllowanceCharge", NS) is not None,
        ))
    return inv
