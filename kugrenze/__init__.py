"""Kleinunternehmer-Grenzwächter: Kontoauszug einlesen, Umsatz kumulieren, Grenzen AT/DE prüfen."""
from .bankcsv import parse_csv, Transaction, CsvError  # noqa: F401
from .rules import evaluate, RULES  # noqa: F401
__version__ = "0.1.0"
