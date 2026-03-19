"""Bombadil Mobile -- property-based testing for mobile UIs.

Re-exports the public API so specs can write::

    from bombadil import extract, always, eventually, now, next_state
    from bombadil import action_generator, weighted
    from bombadil import TapAction, SwipeAction, TypeAction
"""

from bombadil.extractors import extract
from bombadil.properties import always, eventually, now, next_state, Property
from bombadil.actions import (
    TapAction,
    SwipeAction,
    TypeAction,
    LongPressAction,
    BackAction,
    HomeAction,
    BurstAction,
    action_generator,
    weighted,
)

__all__ = [
    "extract",
    "always",
    "eventually",
    "now",
    "next_state",
    "Property",
    "TapAction",
    "SwipeAction",
    "TypeAction",
    "LongPressAction",
    "BackAction",
    "HomeAction",
    "BurstAction",
    "action_generator",
    "weighted",
]
