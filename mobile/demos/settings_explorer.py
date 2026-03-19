#!/usr/bin/env python3
"""Demo 1: Settings Explorer -- zero-setup, runs on iOS Settings.

No app install required. Starts a bare iOS device, opens Settings,
and autonomously explores while checking universal properties.

    python demos/settings_explorer.py --platform ios --max-steps 30
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bombadil import extract, always, now, eventually, TapAction, SwipeAction, BackAction, weighted
from bombadil.engine import ExplorationConfig, ExplorationEngine
from bombadil.reporter import BombadilReporter

# ---------------------------------------------------------------------------
# Extractors
# ---------------------------------------------------------------------------

crash_dialog = extract(
    "Is there a crash dialog, error alert, or system error message visible?",
    returns=bool, name="crash_dialog",
)
blank_screen = extract(
    "Is the screen completely blank or empty with no UI elements?",
    returns=bool, name="blank_screen",
)
loading_spinner = extract(
    "Is there a loading spinner or progress indicator visible?",
    returns=bool, name="loading_spinner",
)
has_settings_content = extract(
    "Are there settings rows, menu items, or configuration options visible on screen?",
    returns=bool, name="has_settings_content",
)

# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

no_crash_dialogs = always(lambda: not crash_dialog.current, name="no_crash_dialogs")
no_blank_screens = always(lambda: not blank_screen.current, name="no_blank_screens")
loading_resolves = always(
    now(lambda: loading_spinner.current).implies(
        eventually(lambda: not loading_spinner.current).within(seconds=5)
    ),
    name="loading_resolves",
)
back_navigation_works = always(
    lambda: has_settings_content.current or not blank_screen.current,
    name="back_navigation_works",
)

PROPERTIES = [no_crash_dialogs, no_blank_screens, loading_resolves, back_navigation_works]
EXTRACTORS = [crash_dialog, blank_screen, loading_spinner, has_settings_content]

# ---------------------------------------------------------------------------
# Action generators
# ---------------------------------------------------------------------------


def tap_settings_rows(device, state):
    """Tap random settings rows to explore different panes."""
    return [
        TapAction(target="any settings row or menu item"),
        TapAction(target="General"),
        TapAction(target="Wi-Fi"),
        TapAction(target="Bluetooth"),
        TapAction(target="Display & Brightness"),
        TapAction(target="Accessibility"),
    ]


def scroll_settings(device, state):
    """Scroll through long settings lists."""
    return [
        SwipeAction(direction="down"),
        SwipeAction(direction="up"),
    ]


def navigate_back(device, state):
    """Go back to the previous settings pane."""
    return [
        BackAction(),
        TapAction(target="Back button or navigation back arrow"),
    ]


ACTIONS = weighted([
    (10, tap_settings_rows),
    (3, scroll_settings),
    (5, navigate_back),
])


def main() -> None:
    parser = argparse.ArgumentParser(description="Bombadil Mobile -- Settings Explorer Demo")
    parser.add_argument("--platform", default="ios", choices=["ios", "android"])
    parser.add_argument("--max-steps", type=int, default=30)
    parser.add_argument("--exit-on-violation", action="store_true")
    args = parser.parse_args()

    config = ExplorationConfig(
        platform=args.platform,
        max_steps=args.max_steps,
        exit_on_first_violation=args.exit_on_violation,
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
