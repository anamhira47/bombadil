"""Built-in default properties -- mirrors Bombadil web's defaults.

These universal properties apply to any mobile app without configuration.
Import them in your spec with::

    from specs.defaults import *
"""

from bombadil import extract, always, eventually, now

# ---------------------------------------------------------------------------
# Extractors
# ---------------------------------------------------------------------------

crash_dialog = extract(
    "Is there a crash dialog, error alert, ANR popup, or 'app has stopped' message visible?",
    returns=bool, name="crash_dialog",
)
blank_screen = extract(
    "Is the screen completely blank, empty, or showing only a solid color with no UI elements?",
    returns=bool, name="blank_screen",
)
loading_spinner = extract(
    "Is there a loading spinner, progress indicator, or skeleton placeholder visible?",
    returns=bool, name="loading_spinner",
)
permission_dialog = extract(
    "Is there an unexpected system permission dialog (location, camera, notifications) visible?",
    returns=bool, name="permission_dialog",
)

# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

no_crash_dialogs = always(
    lambda: not crash_dialog.current,
    name="no_crash_dialogs",
)

no_blank_screens = always(
    lambda: not blank_screen.current,
    name="no_blank_screens",
)

loading_resolves = always(
    now(lambda: loading_spinner.current).implies(
        eventually(lambda: not loading_spinner.current).within(seconds=10)
    ),
    name="loading_resolves",
)

no_permission_dialogs = always(
    lambda: not permission_dialog.current,
    name="no_permission_dialogs",
)

ALL_PROPERTIES = [no_crash_dialogs, no_blank_screens, loading_resolves, no_permission_dialogs]
ALL_EXTRACTORS = [crash_dialog, blank_screen, loading_spinner, permission_dialog]
