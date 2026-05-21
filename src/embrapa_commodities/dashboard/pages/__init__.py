"""Multi-page registration. Pages are imported by `app.py` after `Dash(use_pages=False)`
is constructed; we use a small custom router instead of `dash.register_page` so
the pages can be wired with shared callbacks and a single `GoldStore` instance.
"""
