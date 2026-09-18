import importlib

# Canonical product names, matched case-insensitively against config.ini so
# units still carrying the older lowercase `name=dg5w` keep resolving.
PRODUCTS = ('dg5W', 'dg5R')


def canonical_product(product_name):
    """Return the canonically cased product name, or the input if unknown."""
    name = (product_name or '').strip()
    return next((p for p in PRODUCTS if p.lower() == name.lower()), name)


def load_product(product_name):
    """Load a product profile module by name.

    Args:
        product_name: Product identifier (e.g. 'dg5W', 'dg5R')

    Returns:
        Module with create_sensors(), create_viewers(),
        create_fallback_sensors(), create_fallback_viewers()
    """
    return importlib.import_module(f"profiles.{canonical_product(product_name)}")
