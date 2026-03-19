"""E-commerce app properties -- catches pricing, cart, and navigation bugs.

Targets Bug Bazaar or any generic shopping app.

    python run.py --platform ios --app-url $APP_URL specs/ecommerce.py
"""

from bombadil import (
    extract,
    always,
    action_generator,
    weighted,
    TapAction,
    SwipeAction,
    TypeAction,
    BackAction,
)
from specs.defaults import ALL_PROPERTIES, ALL_EXTRACTORS

# ---------------------------------------------------------------------------
# Extractors
# ---------------------------------------------------------------------------

cart_count = extract(
    "How many items are shown in the shopping cart badge or icon? Return just the number, 0 if none.",
    returns=int, name="cart_count",
)
visible_price = extract(
    "What is the main price displayed on screen in dollars? Return just the number like 29.99, or 0 if no price visible.",
    returns=float, name="visible_price",
)
on_product_detail = extract(
    "Is this a product detail page showing a single product with its price and description?",
    returns=bool, name="on_product_detail",
)
product_has_image = extract(
    "Is there at least one product image visible on the current product detail page?",
    returns=bool, name="product_has_image",
)
screen_title = extract(
    "What is the title or header text of the current screen?",
    returns=str, name="screen_title",
)

# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

cart_never_negative = always(
    lambda: cart_count.current >= 0,
    name="cart_never_negative",
)

prices_always_positive = always(
    lambda: visible_price.current > 0.0 if on_product_detail.current else True,
    name="prices_always_positive",
)

product_detail_has_image = always(
    lambda: product_has_image.current if on_product_detail.current else True,
    name="product_detail_has_image",
)

ECOMMERCE_PROPERTIES = ALL_PROPERTIES + [
    cart_never_negative,
    prices_always_positive,
    product_detail_has_image,
]

ECOMMERCE_EXTRACTORS = ALL_EXTRACTORS + [
    cart_count,
    visible_price,
    on_product_detail,
    product_has_image,
    screen_title,
]

# ---------------------------------------------------------------------------
# Action generators
# ---------------------------------------------------------------------------


@action_generator
def browse_products(device, state):
    """Tap product cards and scroll through product lists."""
    return [
        TapAction(target="any product card or product listing item"),
        SwipeAction(direction="down", target="product list or main content area"),
        SwipeAction(direction="up", target="product list or main content area"),
    ]


@action_generator
def shopping_actions(device, state):
    """Add to cart, view cart, remove items."""
    return [
        TapAction(target="Add to Cart button"),
        TapAction(target="cart icon or cart tab"),
        TapAction(target="Remove or delete button on a cart item"),
    ]


@action_generator
def navigate(device, state):
    """Navigate between screens."""
    return [
        BackAction(),
        TapAction(target="any tab bar item or navigation tab"),
        TapAction(target="any category or filter option"),
    ]


ECOMMERCE_ACTIONS = weighted([
    (10, browse_products),
    (5, shopping_actions),
    (3, navigate),
])
