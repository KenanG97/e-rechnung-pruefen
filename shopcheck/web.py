"""Browser-Brücke (Pyodide) für den Produktdaten-Check."""
from __future__ import annotations

import csv
import io
import json

from .checks import check_product
from .products import ShopCsvError, load_products

_STATE: dict = {"products": [], "results": [], "header": []}


def analyze(data: bytes, limit: int = 0) -> str:
    try:
        products, mapping = load_products(bytes(data))
    except ShopCsvError as e:
        return json.dumps({"ok": False, "error": str(e)})
    total = len(products)
    if limit and total > limit:
        products = products[:limit]
    results = []
    for p in products:
        f, info = check_product(p)
        results.append({"row": p.row, "key": p.key, "title": p.title, "variant": p.variant,
                        "price": str(p.price) if p.price is not None else "", "vendor": p.vendor,
                        "findings": [x.__dict__ for x in f], "info": info})
    _STATE.update(products=products, results=results, header=list(products[0].raw.keys()) if products else [])
    summary = {
        "products": len(results), "total": total, "limited": bool(limit and total > limit),
        "errors": sum(1 for r in results if any(x["severity"] == "fehler" for x in r["findings"])),
        "grundpreis_missing": sum(1 for r in results if any(x["code"] in ("GP-1", "GP-2", "GP-3", "GP-4") for x in r["findings"])),
        "gpsr_missing": sum(1 for r in results if any(x["code"].startswith("PS-") and x["severity"] == "fehler" for x in r["findings"])),
        "ok": sum(1 for r in results if not any(x["severity"] != "info" for x in r["findings"])),
    }
    return json.dumps({"ok": True, "mapping": mapping, "summary": summary, "results": results}, ensure_ascii=False)


def export_fixed() -> str:
    """Original-CSV mit zusätzlicher Spalte „Grundpreis (berechnet)“ und Prüfergebnis."""
    buf = io.StringIO()
    header = _STATE["header"] + ["Grundpreis (berechnet)", "Füllmenge (erkannt)", "Prüfergebnis"]
    w = csv.writer(buf, delimiter=";")
    w.writerow(header)
    for p, r in zip(_STATE["products"], _STATE["results"]):
        codes = ", ".join(f'{x["code"]} {x["message"]}' for x in r["findings"] if x["severity"] != "info")
        w.writerow([p.raw.get(h, "") for h in _STATE["header"]] +
                   [r["info"].get("unit_price_text", ""), r["info"].get("quantity_text", ""), codes or "ok"])
    return "﻿" + buf.getvalue()
