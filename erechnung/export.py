"""Exporte: Positions-CSV, Sammel-CSV (für Steuerberater/Excel) und PDF-Prüfbericht."""
from __future__ import annotations

import csv
import io
from datetime import datetime
from decimal import Decimal
from typing import Optional

from .checks import Finding
from .model import Invoice, TYPE_CODES, UNIT_CODES, VAT_CATEGORIES, PAYMENT_MEANS


def eur(x: Optional[Decimal], cur: str = "EUR") -> str:
    if x is None:
        return "–"
    s = f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} {'€' if cur in ('EUR', '') else cur}"


def de_date(d) -> str:
    return d.strftime("%d.%m.%Y") if d else "–"


def summary_row(inv: Invoice, status: str) -> dict:
    t = inv.totals
    rates = "; ".join(f"{tb.category} {tb.rate or 0}%" for tb in inv.taxes)
    return {
        "Datei": inv.source_name, "Status": status, "Lieferant": inv.seller.name,
        "USt-IdNr. Lieferant": inv.seller.vat_id, "Steuernummer Lieferant": inv.seller.tax_number,
        "Rechnungsnr.": inv.number, "Art": TYPE_CODES.get(inv.type_code, inv.type_code),
        "Rechnungsdatum": de_date(inv.issue_date), "Leistungsdatum": de_date(inv.delivery_date or inv.period_end),
        "Fällig": de_date(inv.due_date), "Währung": inv.currency,
        "Netto": f"{t.tax_basis_total or 0:.2f}".replace(".", ","),
        "USt": f"{t.tax_total or 0:.2f}".replace(".", ","),
        "Brutto": f"{t.grand_total or 0:.2f}".replace(".", ","),
        "Zahlbetrag": f"{t.payable or 0:.2f}".replace(".", ","),
        "Steuersätze": rates, "IBAN": inv.iban, "Verwendungszweck": inv.number,
    }


def to_csv(rows: list[dict]) -> bytes:
    if not rows:
        return b""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), delimiter=";")
    w.writeheader()
    w.writerows(rows)
    return ("﻿" + buf.getvalue()).encode("utf-8")  # BOM -> Excel erkennt UTF-8


def lines_csv(inv: Invoice) -> bytes:
    rows = [{
        "Pos": ln.line_id, "Bezeichnung": ln.name, "Beschreibung": ln.description,
        "Menge": str(ln.quantity or "").replace(".", ","), "Einheit": UNIT_CODES.get(ln.unit, ln.unit),
        "Einzelpreis netto": str(ln.unit_price or "").replace(".", ","),
        "Gesamt netto": str(ln.net_amount or "").replace(".", ","),
        "USt-Kat.": ln.vat_category, "USt %": str(ln.vat_rate or "").replace(".", ","),
    } for ln in inv.lines]
    return to_csv(rows)


def pdf_report(inv: Invoice, findings: list[Finding], verdict: str) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"Prüfbericht {inv.number}")
    ss = getSampleStyleSheet()
    small = ParagraphStyle("small", parent=ss["BodyText"], fontSize=8.5, leading=11)
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9.5, leading=12.5)
    h = ss["Heading2"]
    esc = lambda s: (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")  # noqa: E731

    el = [Paragraph(f"Prüfbericht E-Rechnung {esc(inv.number)}", ss["Title"]),
          Paragraph(f"Erstellt am {datetime.now():%d.%m.%Y %H:%M} · Datei: {esc(inv.source_name)} · "
                    f"{esc(inv.syntax)} / {esc(inv.container)}", small), Spacer(1, 4 * mm),
          Paragraph(f"<b>Ergebnis:</b> {esc(verdict)}", body), Spacer(1, 4 * mm)]

    meta = [
        ["Lieferant", esc(inv.seller.name), "Empfänger", esc(inv.buyer.name)],
        ["Anschrift", esc(inv.seller.address.one_line()), "Anschrift", esc(inv.buyer.address.one_line())],
        ["USt-IdNr./StNr.", esc(inv.seller.vat_id or inv.seller.tax_number), "Käuferreferenz", esc(inv.buyer_reference)],
        ["Rechnungsdatum", de_date(inv.issue_date), "Fällig", de_date(inv.due_date)],
        ["Leistung", de_date(inv.delivery_date) if inv.delivery_date else
         (f"{de_date(inv.period_start)} – {de_date(inv.period_end)}" if inv.period_start or inv.period_end else "–"), "Art", TYPE_CODES.get(inv.type_code, inv.type_code)],
        ["IBAN", esc(inv.iban), "Zahlungsart", PAYMENT_MEANS.get(inv.payment_means_code, inv.payment_means_code)],
    ]
    t = Table([[Paragraph(str(c), small) for c in r] for r in meta], colWidths=[28 * mm, 58 * mm, 28 * mm, 58 * mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                           ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                           ("BACKGROUND", (2, 0), (2, -1), colors.whitesmoke),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    el += [t, Spacer(1, 5 * mm), Paragraph("Befunde", h)]

    if findings:
        rows = [["", "Code", "Befund", "Rechtsgrundlage"]]
        for x in findings:
            rows.append([x.severity.upper(), x.code, Paragraph(esc(x.message), small), Paragraph(esc(x.legal), small)])
        ft = Table(rows, colWidths=[18 * mm, 14 * mm, 108 * mm, 32 * mm], repeatRows=1)
        style = [("GRID", (0, 0), (-1, -1), 0.3, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 8),
                 ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey), ("VALIGN", (0, 0), (-1, -1), "TOP")]
        for i, x in enumerate(findings, start=1):
            c = {"fehler": colors.HexColor("#f8d7da"), "warnung": colors.HexColor("#fff3cd"),
                 "info": colors.HexColor("#e7f1ff")}[x.severity]
            style.append(("BACKGROUND", (0, i), (0, i), c))
        ft.setStyle(TableStyle(style))
        el.append(ft)
    else:
        el.append(Paragraph("Keine Befunde.", body))

    el += [Spacer(1, 5 * mm), Paragraph("Positionen", h)]
    rows = [["Pos", "Bezeichnung", "Menge", "Einzelpreis", "Netto", "USt"]]
    for ln in inv.lines:
        rows.append([esc(ln.line_id)[:10], Paragraph(esc(ln.name), small),
                     f"{ln.quantity or ''} {UNIT_CODES.get(ln.unit, ln.unit)}",
                     eur(ln.unit_price, inv.currency), eur(ln.net_amount, inv.currency),
                     f"{ln.vat_category} {ln.vat_rate or ''}%"])
    lt = Table(rows, colWidths=[14 * mm, 70 * mm, 22 * mm, 24 * mm, 24 * mm, 18 * mm], repeatRows=1)
    lt.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 8),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey), ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
                            ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    el.append(lt)

    tt = inv.totals
    el += [Spacer(1, 4 * mm)]
    sums = [["Summe Positionen", eur(tt.line_total, inv.currency)],
            ["Nettobetrag", eur(tt.tax_basis_total, inv.currency)]]
    for tb in inv.taxes:
        label = f"USt {VAT_CATEGORIES.get(tb.category, tb.category)} {tb.rate or 0} % auf {eur(tb.basis, inv.currency)}"
        sums.append([label, eur(tb.amount, inv.currency)])
    sums += [["Bruttobetrag", eur(tt.grand_total, inv.currency)], ["Zahlbetrag", eur(tt.payable, inv.currency)]]
    st = Table([[Paragraph(esc(a), small), b] for a, b in sums], colWidths=[120 * mm, 52 * mm])
    st.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT"), ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.black),
                            ("FONTSIZE", (0, 0), (-1, -1), 9)]))
    el.append(st)
    el += [Spacer(1, 6 * mm), Paragraph(
        "Hinweis: Dieser Bericht ist eine automatisierte Plausibilitätsprüfung und keine Steuerberatung. "
        "Er ersetzt nicht die formale Validierung gegen die offiziellen KoSIT-Prüfregeln. Bewahren Sie die "
        "Originaldatei (XML bzw. ZUGFeRD-PDF) unverändert auf (GoBD); dieser Bericht ist keine Ersatzarchivierung.",
        small)]
    doc.build(el)
    return buf.getvalue()
