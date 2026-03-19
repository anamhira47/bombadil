# Bombadil Mobile

Property-based testing for mobile UIs -- autonomous exploration with temporal correctness properties, powered by [Revyl](https://revyl.com).

The mobile counterpart to [Bombadil](https://github.com/antithesishq/bombadil) (web). Same temporal logic, same property-based approach. DOM access is replaced by AI vision via the Revyl device SDK.

## Quick Start

```bash
cd mobile
pip install -e .

# Demo 1: Explore iOS Settings (no app install needed)
python demos/settings_explorer.py --platform ios --max-steps 20

# Demo 2: Find bugs in an e-commerce app
python demos/ecommerce_bug_hunt.py --platform ios --app-url $APP_URL --max-steps 50

# Demo 3: Counter state machine (Bombadil's signature demo)
python demos/counter_chaos.py --platform ios --app-url $COUNTER_URL --max-steps 40

# Or use the generic runner with any spec file
python run.py --platform ios specs/defaults.py
python run.py --platform ios --app-url $APP_URL specs/ecommerce.py
```

Prerequisites: `revyl auth login` (authenticate once).

## How It Works

```
                    Web Bombadil                    Mobile Bombadil
                    ───────────                     ───────────────
State observation   DOM queries (querySelector)     AI vision (device.extract)
Actions             Click, type, scroll (CDP)       Tap, type, swipe (Revyl SDK)
Properties          always, eventually, now          Same operators, Python syntax
Exploration         JS coverage-guided              Random weighted + AI grounding
```

### The Exploration Loop

```
1. Start cloud device (DeviceClient.start)
2. Loop:
   a. Screenshot the current screen
   b. Run all extractors (AI answers questions about what's visible)
   c. Check all temporal properties against state history
   d. If violation → record it, save screenshot
   e. Pick a weighted random action from generators
   f. Execute it (tap/swipe/type via Revyl)
   g. Wait for UI to settle
3. Stop device, print report with session recording URL
```

## Writing Specs

A spec is a Python file that defines extractors, properties, and action generators.

### Extractors (observe screen state)

```python
from bombadil import extract

error_visible = extract("Is there an error dialog visible?", returns=bool)
cart_count = extract("How many items in the cart badge?", returns=int)
price = extract("What is the product price in dollars?", returns=float)
```

### Properties (temporal invariants)

```python
from bombadil import always, eventually, now

no_crashes = always(lambda: not error_visible.current)

loading_resolves = always(
    now(lambda: spinner.current).implies(
        eventually(lambda: not spinner.current).within(seconds=10)
    )
)

cart_never_negative = always(lambda: cart_count.current >= 0)
```

### Action Generators (what to try)

```python
from bombadil import TapAction, SwipeAction, action_generator, weighted

@action_generator
def tap_buttons(device, state):
    return [TapAction(target="any button or link on screen")]

@action_generator
def scroll(device, state):
    return [SwipeAction(direction="down")]

actions = weighted([(10, tap_buttons), (3, scroll)])
```

### Running

```bash
python run.py --platform ios --app-url https://... my_spec.py
```

## Web vs Mobile Comparison

| Concept | Web Bombadil (TypeScript) | Mobile Bombadil (Python) |
|---------|--------------------------|--------------------------|
| Extract state | `extract(s => s.document.querySelector(".error"))` | `extract("Is there an error visible?", returns=bool)` |
| Click | `{ Click: { name: "btn", point } }` | `TapAction(target="Sign In button")` |
| Type | `{ TypeText: { text: "hello" } }` | `TypeAction(target="email field", text="hello")` |
| Scroll | `{ ScrollDown: { origin, distance } }` | `SwipeAction(direction="down")` |
| Invariant | `export const p = always(() => ...)` | `p = always(lambda: ...)` |
| Guarantee | `eventually(() => ...).within(5, "seconds")` | `eventually(lambda: ...).within(seconds=5)` |
| Default properties | `export * from "bombadil/defaults"` | `from specs.defaults import *` |

## API Reference

### Properties

- `always(predicate)` -- must hold in every observed state
- `eventually(predicate).within(seconds=N)` -- must become true within N seconds
- `now(predicate)` -- holds in the current state
- `next_state(predicate)` -- holds in the next state
- `.implies(other)`, `.and_(other)`, `.or_(other)`, `.not_()` -- combinators

### Actions

- `TapAction(target="...")` -- tap an AI-grounded element
- `SwipeAction(direction="up|down|left|right", target="...")` -- swipe gesture
- `TypeAction(target="...", text="...")` -- type into a field
- `LongPressAction(target="...")` -- long press
- `BackAction()` -- back/navigate up
- `HomeAction()` -- return to home screen

### Engine

```python
from bombadil.engine import ExplorationConfig, ExplorationEngine

config = ExplorationConfig(
    platform="ios",
    max_steps=50,
    settle_time_ms=1000,
    exit_on_first_violation=True,
    app_url="https://...",
)

engine = ExplorationEngine(
    properties=[...],
    action_source=weighted_actions,
    config=config,
)

result = engine.run()
print(result.violations)
print(result.session_report_url)
```

## License

MIT -- same as Bombadil.
