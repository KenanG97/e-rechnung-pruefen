"""Browser-Brücke (Pyodide) für den SEPA-Lastschrift-Generator."""
from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime

from kugrenze.bankcsv import parse_day

from .core import Creditor, add_target_days, build_pain008, prenotification_text, validate
from .members import MemberError, load_members

_S: dict = {}


def run(data: bytes, filename: str, cfg_json: str, limit: int = 0) -> str:
    cfg = json.loads(cfg_json)
    try:
        debits, mapping = load_members(bytes(data), filename, cfg.get("amount", ""), cfg.get("purpose", ""))
    except MemberError as e:
        return json.dumps({"ok": False, "error": str(e)})
    total = len(debits)
    limited = bool(limit and total > limit)
    if limited:
        debits = debits[:limit]
    cred = Creditor(name=cfg.get("name", ""), iban=cfg.get("iban", ""), creditor_id=cfg.get("ci", ""), bic=cfg.get("bic", ""),
                    town=cfg.get("town", ""), country=cfg.get("country", ""))
    coll = parse_day(cfg.get("date", "")) or add_target_days(date.today(), 14)
    head = validate(cred, debits, coll)
    hard = [h for h in head if not h.startswith("WARNUNG")]
    ok = [d for d in debits if not d.errors]
    xml = None
    if not hard and ok:
        msg_id = f"LS{datetime.now():%Y%m%d%H%M%S}"
        xml = build_pain008(cred, debits, coll, msg_id).decode("utf-8")
    _S.update(cred=cred, debits=debits, coll=coll)
    return json.dumps({
        "ok": True, "mapping": mapping, "head": head, "collection": coll.isoformat(), "total": total, "limited": limited,
        "count_ok": len(ok), "sum_ok": f"{sum((d.amount for d in ok), 0):.2f}",
        "rows": [{"row": d.row, "name": d.name, "iban": d.iban, "amount": f"{d.amount:.2f}" if d.amount is not None else "",
                  "mandate": d.mandate_id, "seq": d.seq, "errors": d.errors, "warnings": d.warnings} for d in debits],
        "xml": xml,
    }, ensure_ascii=False)


def prenotifications() -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Name", "E-Mail", "Betrag", "Einzugsdatum", "Mandatsreferenz", "Text"])
    for d in _S.get("debits", []):
        if d.errors:
            continue
        w.writerow([d.name, d.email, f"{d.amount:.2f}".replace(".", ","), f"{_S['coll']:%d.%m.%Y}", d.mandate_id,
                    prenotification_text(_S["cred"], d, _S["coll"])])
    return "﻿" + buf.getvalue()
