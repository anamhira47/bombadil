#!/usr/bin/env python3
"""Demo 2: E-Commerce Bug Hunt -- finds real bugs in Bug Bazaar.

Requires an app URL. Autonomously browses products, adds to cart,
and checks pricing/cart invariants.

    python demos/ecommerce_bug_hunt.py --platform ios --app-url $BUG_BAZAAR_URL --max-steps 50
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BUG_BAZAAR_BUILDS = {
    "android": "https://pub-b03f222a53c447c18ef5f8d365a2f00e.r2.dev/bug-bazaar/bug-bazaar-preview.apk",
    "ios": "https://pub-b03f222a53c447c18ef5f8d365a2f00e.r2.dev/bug-bazaar/bug-bazaar-preview-simulator.tar.gz",
}

from bombadil import (
    extract, always, now, eventually,
    TapAction, SwipeAction, TypeAction, BackAction,
    weighted,
)
from bombadil.engine import ExplorationConfig, ExplorationEngine
from bombadil.reporter import BombadilReporter

# ---------------------------------------------------------------------------
# Extractors
# ---------------------------------------------------------------------------

crash_dialog = extract(
    "Is there a crash dialog, error alert, or app-stopped message visible?",
    returns=bool, name="crash_dialog",
)
loading_spinner = extract(
    "Is there a loading spinner or skeleton screen visible?",
    returns=bool, name="loading_spinner",
)
cart_count = extract(
    "How many items are shown in the shopping cart badge? Return 0 if none.",
    returns=int, name="cart_count",
)
visible_price = extract(
    "What is the main product price on screen in dollars? Return the number only (e.g. 29.99), or 0 if no price.",
    returns=float, name="visible_price",
)
on_product_page = extract(
    "Is this a product detail page showing a single product with price and description?",
    returns=bool, name="on_product_page",
)
product_has_image = extract(
    "Is there a product image visible on this product detail page?",
    returns=bool, name="product_has_image",
)

# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

no_crashes = always(lambda: not crash_dialog.current, name="no_crash_dialogs")
loading_resolves = always(
    now(lambda: loading_spinner.current).implies(
        eventually(lambda: not loading_spinner.current).within(seconds=10)
    ),
    name="loading_resolves",
)
cart_never_negative = always(lambda: cart_count.current >= 0, name="cart_never_negative")
prices_always_positive = always(
    lambda: visible_price.current > 0.0 if on_product_page.current else True,
    name="prices_always_positive",
)
product_detail_has_image = always(
    lambda: product_has_image.current if on_product_page.current else True,
    name="product_detail_has_image",
)

PROPERTIES = [no_crashes, loading_resolves, cart_never_negative, prices_always_positive, product_detail_has_image]
EXTRACTORS = [crash_dialog, loading_spinner, cart_count, visible_price, on_product_page, product_has_image]

# ---------------------------------------------------------------------------
# Action generators
# ---------------------------------------------------------------------------


def browse_products(device, state):
    return [
        TapAction(target="any product card or listing item"),
        SwipeAction(direction="down", target="product list or main content"),
        SwipeAction(direction="up", target="product list or main content"),
    ]


def shopping_actions(device, state):
    return [
        TapAction(target="Add to Cart button"),
        TapAction(target="cart icon or cart tab"),
        TapAction(target="Remove or delete button on a cart item"),
    ]


def navigate(device, state):
    return [
        BackAction(),
        TapAction(target="any tab bar item or bottom navigation tab"),
        TapAction(target="any category or filter option"),
    ]


def search(device, state):
    return [
        TapAction(target="search bar or search icon"),
        TypeAction(target="search input field", text="shirt"),
    ]


ACTIONS = weighted([
    (10, browse_products),
    (5, shopping_actions),
    (3, navigate),
    (2, search),
])


def main() -> None:
    parser = argparse.ArgumentParser(description="Bombadil Mobile -- E-Commerce Bug Hunt")
    parser.add_argument("--platform", default="ios", choices=["ios", "android"])
    parser.add_argument("--app-url", default=os.environ.get("DEMO_APP_URL", os.environ.get("BUG_BAZAAR_URL")))
    parser.add_argument("--app-id", default=None)
    parser.add_argument("--max-steps", type=int, default=50)
    parser.add_argument("--exit-on-violation", action="store_true")
    args = parser.parse_args()

    if not args.app_url and not args.app_id:
        args.app_url = BUG_BAZAAR_BUILDS.get(args.platform)
        if not args.app_url:
            print("Error: provide --app-url or --app-id, or set BUG_BAZAAR_URL env var")
            sys.exit(1)
        print(f"Using built-in Bug Bazaar build for {args.platform}")

    config = ExplorationConfig(
        platform=args.platform,
        max_steps=args.max_steps,
        exit_on_first_violation=args.exit_on_violation,
        app_url=args.app_url,
        app_id=args.app_id,
        open_viewer=True,
    )

    engine = ExplorationEngine(
        properties=PROPERTIES,
        action_source=ACTIONS,
        extractors=EXTRACTORS,
        config=config,
        reporter=BombadilReporter(verbose=True),
    )

    result = engine.run()
    sys.exit(1 if result.violations else 0)


if __name__ == "__main__":
    main()
