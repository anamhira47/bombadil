#!/usr/bin/env python3
"""Demo 3: Counter Chaos -- state machine property on a counter app.

Mirrors Bombadil web's signature counter demo. The property says the counter
can only change by +1, -1, or stay the same. Rapid tapping exposes race
conditions that cause the counter to jump by 2.

    python demos/counter_chaos.py --platform ios --app-url $COUNTER_APP_URL --max-steps 40
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bombadil import extract, always, TapAction, BurstAction, weighted
from bombadil.engine import ExplorationConfig, ExplorationEngine
from bombadil.reporter import BombadilReporter

# ---------------------------------------------------------------------------
# Extractors
# ---------------------------------------------------------------------------

counter_value = extract(
    "What number is displayed on the counter? Return just the integer.",
    returns=int, name="counter_value",
)
crash_dialog = extract(
    "Is there a crash dialog or error alert visible?",
    returns=bool, name="crash_dialog",
)

# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

counter_changes_by_one = always(
    lambda: abs(counter_value.current - counter_value.previous) <= 1,
    name="counter_changes_by_one",
)

counter_never_negative = always(
    lambda: counter_value.current >= 0,
    name="counter_never_negative",
)

no_crashes = always(
    lambda: not crash_dialog.current,
    name="no_crash_dialogs",
)

PROPERTIES = [counter_changes_by_one, counter_never_negative, no_crashes]
EXTRACTORS = [counter_value, crash_dialog]

# ---------------------------------------------------------------------------
# Action generators
# ---------------------------------------------------------------------------


def tap_increment(device, state):
    """Tap the increment/plus button."""
    return [TapAction(target="increment button or plus button or + button")]


def tap_decrement(device, state):
    """Tap the decrement/minus button."""
    return [TapAction(target="decrement button or minus button or - button")]


def tap_reset(device, state):
    """Tap the reset button."""
    return [TapAction(target="reset button or clear button")]


def rapid_double_tap(device, state):
    """Rapid double-tap increment to test race conditions."""
    return [
        BurstAction([
            TapAction(target="increment button or plus button or + button"),
            TapAction(target="increment button or plus button or + button"),
        ])
    ]


ACTIONS = weighted([
    (10, tap_increment),
    (5, tap_decrement),
    (1, tap_reset),
    (3, rapid_double_tap),
])


def main() -> None:
    parser = argparse.ArgumentParser(description="Bombadil Mobile -- Counter Chaos Demo")
    parser.add_argument("--platform", default="ios", choices=["ios", "android"])
    parser.add_argument("--app-url", default=os.environ.get("COUNTER_APP_URL"))
    parser.add_argument("--app-id", default=None)
    parser.add_argument("--max-steps", type=int, default=40)
    parser.add_argument("--exit-on-violation", action="store_true")
    args = parser.parse_args()

    if not args.app_url and not args.app_id:
        print("Error: provide --app-url or --app-id, or set COUNTER_APP_URL env var")
        sys.exit(1)

    config = ExplorationConfig(
        platform=args.platform,
        max_steps=args.max_steps,
        settle_time_ms=500,
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
