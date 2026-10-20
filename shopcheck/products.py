"""Produkt-CSV aus Shopify, WooCommerce, Etsy oder beliebigen Shops einlesen.

Spalten werden über typische Bezeichnungen (deutsch/englisch) erkannt. Bei Shopify stehen
Varianten in eigenen Zeilen mit gleichem „Handle“; Titel, Beschreibung und Hersteller stehen
nur in der ersten Zeile und werden auf die Varianten vererbt.
"""
from __future__ import annotations

import csv
import html
import io
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from kugrenze.bankcsv import parse_amount  # gleicher robuster Zahlenleser

csv.field_size_limit(10 * 1024 * 1024)


class ShopCsvError(Exception):
    pass


@dataclass
class Product:
    row: int
    key: str                 # Handle/ID/SKU
    title: str
    variant: str = ""
    price: Optional[Decimal] = None
    description: str = ""    # Klartext
    vendor: str = ""
    manufacturer_text: str = ""   # alles, was nach Herstellerangaben aussieht
    unit_price_text: str = ""     # vorhandene Grundpreisangabe
    grams: Optional[Decimal] = None
    image: str = ""
    sku: str = ""
    category: str = ""
    raw: dict = field(default_factory=dict)


SYN = {
    "key": ["handle", "id", "listing_id", "artikelnummer", "produkt-id", "product id"],
    "title": ["title", "titel", "name", "produktname", "artikelname", "bezeichnung", "product name"],
    "variant": ["option1 value", "option1 wert", "variante", "variant", "attribut 1 wert(e)", "attribute 1 value(s)"],
    "price": ["variant price", "preis", "price", "regulärer preis", "regular price", "verkaufspreis", "vk-preis", "bruttopreis"],
    "description": ["body (html)", "body html", "beschreibung", "description", "produktbeschreibung", "kurzbeschreibung", "short description"],
    "vendor": ["vendor", "hersteller", "manufacturer", "marke", "brand", "marken", "brands", "anbieter"],
    "grams": ["variant grams", "gewicht (g)", "gewicht in gramm"],
    "kg": ["gewicht (kg)", "weight (kg)", "gewicht"],
    "image": ["image src", "bilder", "images", "image1", "bild", "image", "bild-url", "image url"],
    "sku": ["variant sku", "sku", "artikelnummer", "ean", "gtin"],
    "category": ["product category", "type", "kategorien", "kategorie", "categories", "tags"],
}
UNIT_PRICE_HINTS = ["grundpreis", "unit price", "unit_price", "preis pro", "price per"]
MANUFACTURER_HINTS = ["hersteller", "manufacturer", "gpsr", "verantwortliche person", "responsible person", "produktsicherheit",
                      "product safety", "inverkehrbringer", "importeur", "importer"]


def _text(s: str) -> str:
    s = re.sub(r"<(br|/p|/div|/li|/h\d)\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"[ \t ]+", " ", s).strip()


def _col(header_norm: list[str], keys: list[str], used: set[int]) -> Optional[int]:
    for k in keys:
        if k in header_norm and header_norm.index(k) not in used:
            return header_norm.index(k)
    for k in keys:
        for i, h in enumerate(header_norm):
            if i not in used and (h.startswith(k) or f" {k}" in f" {h}"):
                return i
    return None


def load_products(data: bytes) -> tuple[list[Product], dict]:
    if len(data) > 30 * 1024 * 1024:
        raise ShopCsvError("Datei ist größer als 30 MB.")
    for enc in ("utf-8-sig", "cp1252"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ShopCsvError("Zeichenkodierung nicht erkannt.")
    first = text.split("\n", 1)[0]
    delim = max((";", ",", "\t"), key=first.count)
    rows = list(csv.reader(io.StringIO(text), delimiter=delim))
    if len(rows) < 2:
        raise ShopCsvError("Keine Produkte gefunden.")
    header = rows[0]
    hn = [h.strip().lower() for h in header]
    used: set[int] = set()
    cols = {}
    for k in ("key", "title", "variant", "price", "description", "vendor", "grams", "kg", "image", "sku", "category"):
        c = _col(hn, SYN[k], used)
        # „name“ darf nicht die Spalte „Option1 Name“ treffen
        if c is not None and k == "title" and "option" in hn[c]:
            c = None
        cols[k] = c
        if c is not None:
            used.add(c)
    if cols["title"] is None:
        raise ShopCsvError("Keine Spalte mit Produktnamen gefunden (z. B. „Title“, „Name“, „Titel“).")
    up_cols = [i for i, h in enumerate(hn) if any(x in h for x in UNIT_PRICE_HINTS)]
    mf_cols = [i for i, h in enumerate(hn) if any(x in h for x in MANUFACTURER_HINTS) and i != cols["vendor"]]

    platform = ("Shopify" if "handle" in hn and "variant price" in hn else
                "WooCommerce" if any(h in hn for h in ("regulärer preis", "regular price")) else
                "Etsy" if "image1" in hn and "currency_code" in hn else "allgemein")

    out: list[Product] = []
    parent: dict[str, Product] = {}
    for n, r in enumerate(rows[1:], start=2):
        if not any(c.strip() for c in r):
            continue
        g = lambda i: (r[i].strip() if i is not None and i < len(r) else "")  # noqa: E731
        key = g(cols["key"]) or g(cols["sku"]) or f"Zeile {n}"
        title = g(cols["title"])
        par = parent.get(key)
        if not title and par is None:
            continue  # reine Bildzeilen o. Ä.
        if not title and platform == "Shopify" and not g(cols["price"]):
            continue  # zusätzliche Bildzeile einer Shopify-Variante
        grams = None
        if cols["grams"] is not None and g(cols["grams"]):
            grams = parse_amount(g(cols["grams"]))
        elif cols["kg"] is not None and g(cols["kg"]):
            kg = parse_amount(g(cols["kg"]))
            grams = kg * 1000 if kg is not None else None
        p = Product(
            row=n, key=key, title=title or (par.title if par else ""), variant=g(cols["variant"]),
            price=parse_amount(g(cols["price"])),
            description=_text(g(cols["description"])) or (par.description if par else ""),
            vendor=g(cols["vendor"]) or (par.vendor if par else ""),
            manufacturer_text=" | ".join(_text(g(i)) for i in mf_cols if g(i)) or (par.manufacturer_text if par else ""),
            unit_price_text=" ".join(g(i) for i in up_cols if g(i)),
            grams=grams, image=g(cols["image"]) or (par.image if par else ""), sku=g(cols["sku"]),
            category=g(cols["category"]) or (par.category if par else ""),
            raw={header[i]: (r[i] if i < len(r) else "") for i in range(len(header))},
        )
        if title:
            parent[key] = p
        if p.variant.lower() in ("default title", "standardtitel"):
            p.variant = ""
        out.append(p)
    if not out:
        raise ShopCsvError("Keine Produkte gefunden.")
    mapping = {"Plattform": platform, "Name": header[cols["title"]],
               "Preis": header[cols["price"]] if cols["price"] is not None else "–",
               "Hersteller/Marke": header[cols["vendor"]] if cols["vendor"] is not None else "–",
               "Herstellerangaben": ", ".join(header[i] for i in mf_cols) or "aus Beschreibung",
               "Grundpreis-Spalten": ", ".join(header[i] for i in up_cols) or "keine"}
    return out, mapping
