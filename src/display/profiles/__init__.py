import importlib


def load_product(product_name):
    """Load a product profile module by name.

    Args:
        product_name: Product identifier (e.g. 'dg5w', 'dg5r')

    Returns:
        Module with create_sensors(), create_viewers(),
        create_fallback_sensors(), create_fallback_viewers()
    """
    return importlib.import_module(f"profiles.{product_name}")
