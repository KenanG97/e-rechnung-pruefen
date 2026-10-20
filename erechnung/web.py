"""Brücke für den Browser (Pyodide): eine Funktion, JSON rein, JSON raus."""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal

from .checks import check_against_history, check_invoice, summarize
from .export import lines_csv, summary_row
from .model import PAYMENT_MEANS, TYPE_CODES, UNIT_CODES, VAT_CATEGORIES
from .parser import ParseError, parse_bytes


def _default(o):
    if isinstance(o, Decimal):
        return str(o)
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    raise TypeError(type(o))


def analyze(data: bytes, name: str, history_json: str = "[]") -> str:
    try:
        history = json.loads(history_json or "[]")
    except ValueError:
        history = []
    h = hashlib.sha256(data).hexdigest()
    try:
        inv = parse_bytes(bytes(data), name)
    except ParseError as exc:
        return json.dumps({"ok": False, "name": name, "error": str(exc), "hash": h})
    inv._hash = h
    findings = check_against_history(inv, history) + check_invoice(inv)
    color, text = summarize(findings)
    d = inv.to_dict()
    d["type_label"] = TYPE_CODES.get(inv.type_code, "Rechnung")
    d["payment_label"] = PAYMENT_MEANS.get(inv.payment_means_code, inv.payment_means_code)
    for ln in d["lines"]:
        ln["unit_label"] = UNIT_CODES.get(ln["unit"], ln["unit"])
    for tb in d["taxes"]:
        tb["category_label"] = VAT_CATEGORIES.get(tb["category"], tb["category"])
    record = {
        "checked_at": datetime.now().isoformat(timespec="seconds"), "hash": h,
        "seller_name": inv.seller.name, "seller_vat": inv.seller.vat_id, "seller_tax": inv.seller.tax_number,
        "number": inv.number, "payable": str(inv.totals.payable or ""),
        "iban": inv.iban.replace(" ", "").upper(), "status": color,
    }
    return json.dumps({
        "ok": True, "name": name, "hash": h, "invoice": d, "verdict": {"color": color, "text": text},
        "findings": [{"severity": f.severity, "code": f.code, "message": f.message, "legal": f.legal}
                     for f in findings],
        "history_record": record,
        "summary_row": summary_row(inv, color),
        "lines_csv": lines_csv(inv).decode("utf-8"),
    }, default=_default, ensure_ascii=False)
