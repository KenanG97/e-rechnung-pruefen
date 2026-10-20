"""Lokaler Verlauf geprüfter Rechnungen (SQLite).

Gespeichert werden NUR Metadaten (Lieferant, Nummer, Betrag, IBAN, Hash) – nie die Datei.
Damit funktionieren Duplikat- und IBAN-Wechsel-Erkennung, ohne sensible Dokumente zu horten.
"""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path

from .model import Invoice

SCHEMA = """
CREATE TABLE IF NOT EXISTS checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    checked_at TEXT NOT NULL,
    hash TEXT NOT NULL,
    seller_name TEXT, seller_vat TEXT, seller_tax TEXT,
    number TEXT, issue_date TEXT, due_date TEXT,
    currency TEXT, payable TEXT, iban TEXT,
    status TEXT, errors INTEGER, warnings INTEGER
);
CREATE INDEX IF NOT EXISTS ix_seller ON checks(seller_vat, seller_tax, seller_name);
"""


def file_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class History:
    def __init__(self, path: str | Path):
        self.path = str(path)
        with self._conn() as c:
            c.executescript(SCHEMA)

    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def all(self) -> list[dict]:
        with self._conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM checks ORDER BY id DESC")]

    def add(self, inv: Invoice, status: str, errors: int, warnings: int) -> None:
        with self._conn() as c:
            if c.execute("SELECT 1 FROM checks WHERE hash=?", (inv._hash,)).fetchone():
                return
            c.execute(
                "INSERT INTO checks (checked_at, hash, seller_name, seller_vat, seller_tax, number,"
                " issue_date, due_date, currency, payable, iban, status, errors, warnings)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (datetime.now().isoformat(timespec="seconds"), inv._hash, inv.seller.name,
                 inv.seller.vat_id, inv.seller.tax_number, inv.number,
                 inv.issue_date.isoformat() if inv.issue_date else "",
                 inv.due_date.isoformat() if inv.due_date else "",
                 inv.currency, str(inv.totals.payable or ""), inv.iban.replace(" ", "").upper(),
                 status, errors, warnings),
            )

    def clear(self) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM checks")
