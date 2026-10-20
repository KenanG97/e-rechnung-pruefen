"""Produktdaten-Check für Online-Shops: Grundpreis (PAngV) und GPSR-Pflichtangaben."""
from .products import load_products, Product, ShopCsvError  # noqa: F401
from .checks import check_product, parse_quantity, unit_price  # noqa: F401
__version__ = "0.1.0"
