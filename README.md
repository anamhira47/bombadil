# Bombadil

Property-based testing for web UIs, autonomously exploring and validating
correctness properties, *finding harder bugs earlier*.

Runs in your local developer environment, in CI, and inside Antithesis.

> [!NOTE]
> Bombadil is new and experimental. Stuff is going to change in the early days. Even so, we hope you'll try it out!

## Documentation

Learn all about Bombadil with the following resources:

* [The Bombadil Manual](https://antithesishq.github.io/bombadil/)
* [Installation](https://antithesishq.github.io/bombadil/2-getting-started.html#installation)
* [Examples](https://antithesishq.github.io/bombadil/3-specification-language.html#examples)

Or, if you want to hack on it, see [Contributing](docs/development/contributing.md).

<hr>

## Bombadil Mobile

Property-based testing for **mobile UIs** -- the same temporal logic, same autonomous exploration, applied to iOS and Android apps.

Bombadil works on web because browsers expose the DOM. Mobile apps are opaque pixels -- there's no `querySelector` for an iPhone. Bombadil Mobile replaces DOM access with AI vision: instead of querying the DOM for an error dialog, you ask *"Is there an error dialog visible?"* and an AI model reads the screenshot.

Device interaction is powered by [Revyl](https://www.revyl.ai) -- cloud-hosted iOS and Android devices with AI-grounded element targeting, live streaming, and a Python SDK for programmatic control.

### The core translation

```
Web Bombadil                              Mobile Bombadil
─────────────                             ───────────────
extract(s => s.document                   extract("Is there an error
  .querySelector(".error"))                 dialog visible?", returns=bool)

{ Click: { name: "btn", point } }         TapAction(target="Sign In button")

{ TypeText: { text: "hello" } }           TypeAction(target="email", text="hello")

{ ScrollDown: { origin, distance } }      SwipeAction(direction="down")

always(() => count.current <= 5)          always(lambda: count.current <= 5)
```

The temporal operators (`always`, `eventually`, `now`, `next_state`) and their semantics are identical. Only the observation and action layers change.

### How it works

1. Start a cloud-hosted iOS/Android device
2. **Observe** -- screenshot the screen, run AI extractors to answer questions about what's visible
3. **Check** -- evaluate all temporal properties against the state history
4. **Act** -- pick a weighted random action (tap, swipe, type) and execute it
5. Repeat until max steps or a violation is found
6. Print report with session recording URL

### Writing a spec

A spec is a Python file. 15 lines defines a full property-based test:

```python
from bombadil import extract, always, eventually, now, TapAction, SwipeAction, weighted

# Observe -- AI reads the screen
error_dialog = extract("Is there an error dialog visible?", returns=bool, name="error_dialog")
loading      = extract("Is there a loading spinner?", returns=bool, name="loading")
cart_count   = extract("How many items in the cart badge?", returns=int, name="cart_count")

# Properties -- what must always be true
no_crashes       = always(lambda: not error_dialog.current, name="no_crashes")
loading_resolves = always(
    now(lambda: loading.current).implies(
        eventually(lambda: not loading.current).within(seconds=10)
    ),
    name="loading_resolves",
)
cart_valid = always(lambda: cart_count.current >= 0, name="cart_never_negative")
```

No step-by-step scripts. No selectors to maintain. The properties are resilient to UI redesigns because they describe *what should be true*, not *how to navigate*.

### Demo: exploring iOS Settings

Zero setup required -- no app to install, no credentials. Bombadil Mobile starts a cloud iOS device, opens Settings, and autonomously explores while checking properties:

```
$ python demos/settings_explorer.py --platform ios --max-steps 10

╭──────────────────────── Tom Bombadil ────────────────────────╮
│ Bombadil Mobile -- Property-Based Testing                    │
│                                                              │
│ Platform: ios  |  Max steps: 10  |  Properties: 4            │
╰──────────────────────────────────────────────────────────────╯

  Live viewer: https://app.revyl.ai/tests/execute?workflowRunId=...

──────────────────────── Step 1/10 ─────────────────────────────
  extract: crash_dialog = False
  extract: blank_screen = False
  extract: loading_spinner = False
  extract: has_settings_content = True
  PASS  no_crash_dialogs
  PASS  no_blank_screens
  PASS  loading_resolves
  PASS  back_navigation_works
  action: Tap "Display & Brightness"

──────────────────────── Step 2/10 ─────────────────────────────
  extract: crash_dialog = False
  extract: blank_screen = False
  extract: loading_spinner = False
  extract: has_settings_content = True
  PASS  no_crash_dialogs
  PASS  no_blank_screens
  PASS  loading_resolves
  PASS  back_navigation_works
  action: Tap "General"
  ...

──────────────── Exploration Complete ──────────────────────────

          Summary
┌────────────────┬────────┐
│ Steps executed │ 7      │
│ Duration       │ 502.3s │
│ Violations     │ 0      │
└────────────────┴────────┘

All properties held. No bugs found.
```

The live viewer URL streams the device screen in real time. Here are recordings from actual runs:

| Run | App | Steps | Properties | Violations | Session Recording |
|-----|-----|-------|------------|------------|-------------------|
| Settings Explorer | iOS Settings | 10 | 4 | 0 | [Watch recording](https://app.revyl.ai/tests/execute?workflowRunId=63e26c65-02da-40c3-9c41-8f545a344236&platform=ios) |
| E-Commerce Bug Hunt | Bug Bazaar | 15 | 5 | 0 | [Watch recording](https://app.revyl.ai/tests/execute?workflowRunId=6b6ad57b-8531-4b8d-b29c-42aa79dd5fcc&platform=ios) |

Each recording shows the full device screen with every tap, swipe, and navigation that Bombadil performed autonomously.

### Demo: finding bugs in an e-commerce app

Point Bombadil at a real app and define domain-specific properties. It explores randomly, and when it hits an edge case no human would test, the property catches it:

```python
prices_always_positive = always(
    lambda: visible_price.current > 0.0 if on_product_page.current else True,
    name="prices_always_positive",
)
```

```
$ python demos/ecommerce_bug_hunt.py --platform ios --max-steps 50
  ...
  action: Tap "any product card or listing item"
  action: Swipe down on "product list or main content"
  action: Tap "Add to Cart button"
  action: Tap "cart icon or cart tab"
  ...
```

### Running

```bash
cd mobile
pip install -e .
revyl auth login  # one-time authentication

# Settings explorer (zero setup)
python demos/settings_explorer.py --platform ios --max-steps 20

# E-commerce bug hunt (uses built-in Bug Bazaar app)
python demos/ecommerce_bug_hunt.py --platform ios --max-steps 50

# Counter state machine (Bombadil's classic demo, mobile edition)
python demos/counter_chaos.py --platform ios --app-url $COUNTER_URL --max-steps 40

# Generic runner with any spec file
python run.py --platform ios --app-url https://... specs/ecommerce.py
```

Full technical reference: [`mobile/README.md`](mobile/README.md)

<hr>

<img alt="Tom Bombadil" src="docs/development/tom.png" width=360 />

> Old Tom Bombadil is a merry fellow,<br>
> Bright blue his jacket is, and his boots are yellow.<br>
> Bugs have never fooled him yet, for Tom, he is the Master:<br>
> His specs are stronger specs, and his fuzzer is faster.

Built by [Antithesis](https://antithesis.com). Mobile extension by [Revyl](https://revyl.com).
