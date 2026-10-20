"""Browser-Brücke (Pyodide) für den Grenzwächter."""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal, InvalidOperation

from .bankcsv import CsvError, Transaction, parse_amount, parse_csv
from .rules import classify, evaluate

_STATE: dict = {"tx": [], "mapping": {}}


def _j(o):
    if isinstance(o, Decimal):
        return float(o)
    if isinstance(o, date):
        return o.isoformat()
    raise TypeError(type(o))


def load(data: bytes, own_names: str = "") -> str:
    try:
        tx, mapping = parse_csv(bytes(data))
    except CsvError as e:
        return json.dumps({"ok": False, "error": str(e)})
    classify(tx, [n for n in own_names.split(",")])
    _STATE["tx"] = _STATE["tx"] + tx  # mehrere Konten möglich
    _STATE["mapping"] = mapping
    return json.dumps({"ok": True, "mapping": mapping, "added": len(tx), **_tx_payload()}, default=_j, ensure_ascii=False)


def reset() -> None:
    _STATE["tx"] = []


def toggle(index: int, include: bool) -> None:
    t = _STATE["tx"][index]
    t.include = bool(include) and t.amount > 0
    t.reason = ("manuell gezählt" if t.include else "manuell ausgeschlossen") if t.amount > 0 else t.reason


def _tx_payload() -> dict:
    return {"transactions": [{"i": i, "day": t.day, "amount": t.amount, "party": t.counterparty, "text": t.text[:160],
                              "include": t.include, "reason": t.reason, "tags": t.tags}
                             for i, t in enumerate(_STATE["tx"]) if t.amount > 0],
            "years": sorted({t.day.year for t in _STATE["tx"]}, reverse=True)}


def run(country: str, year: int, prior: str = "", founding: bool = False, extra: str = "", charged_vat: bool = False) -> str:
    def dec(s):
        v = parse_amount(s) if s else None
        return v
    res = evaluate(_STATE["tx"], country, int(year), prior_year_turnover=dec(prior), founding_year=bool(founding),
                   extra_turnover=dec(extra) or Decimal(0), charged_vat=bool(charged_vat))
    return json.dumps({"ok": True, "result": res, **_tx_payload()}, default=_j, ensure_ascii=False)
