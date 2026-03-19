"""Mobile action generators for autonomous exploration.

Defines action types (tap, swipe, type, etc.) and a weighted random
selection mechanism that mirrors Bombadil web's action generators.

Example::

    from bombadil import TapAction, SwipeAction, action_generator, weighted

    @action_generator
    def tap_buttons(device, state):
        return [TapAction(target="any button or link")]

    @action_generator
    def scroll(device, state):
        return [SwipeAction(direction="down")]

    actions = weighted([(10, tap_buttons), (3, scroll)])
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional


class Action(ABC):
    """Base class for all mobile actions.

    Each subclass knows how to execute itself against a DeviceClient.
    """

    @abstractmethod
    def execute(self, device: Any) -> dict:
        """Execute this action on the given device.

        Args:
            device: A revyl DeviceClient instance.

        Returns:
            Response dict from the Revyl CLI.
        """
        ...

    @abstractmethod
    def describe(self) -> str:
        """Human-readable description of this action for logging."""
        ...


class TapAction(Action):
    """Tap an element identified by natural-language target.

    Args:
        target: AI-grounded description of the element to tap.
    """

    def __init__(self, target: str) -> None:
        self.target = target

    def execute(self, device: Any) -> dict:
        return device.tap(target=self.target)

    def describe(self) -> str:
        return f'Tap "{self.target}"'


class SwipeAction(Action):
    """Swipe in a direction, optionally from a target element.

    Args:
        direction: One of "up", "down", "left", "right".
        target: Optional AI-grounded element to swipe from.
    """

    def __init__(self, direction: str, target: Optional[str] = None) -> None:
        self.direction = direction
        self.target = target

    def execute(self, device: Any) -> dict:
        kwargs: dict[str, Any] = {"direction": self.direction}
        if self.target:
            kwargs["target"] = self.target
        return device.swipe(**kwargs)

    def describe(self) -> str:
        base = f"Swipe {self.direction}"
        return f'{base} on "{self.target}"' if self.target else base


class TypeAction(Action):
    """Type text into a field identified by natural-language target.

    Args:
        target: AI-grounded description of the input field.
        text: The text to type.
    """

    def __init__(self, target: str, text: str) -> None:
        self.target = target
        self.text = text

    def execute(self, device: Any) -> dict:
        return device.type_text(target=self.target, text=self.text)

    def describe(self) -> str:
        return f'Type "{self.text}" into "{self.target}"'


class LongPressAction(Action):
    """Long-press an element.

    Args:
        target: AI-grounded description of the element.
        duration_ms: Hold duration in milliseconds.
    """

    def __init__(self, target: str, duration_ms: int = 1500) -> None:
        self.target = target
        self.duration_ms = duration_ms

    def execute(self, device: Any) -> dict:
        return device.long_press(target=self.target, duration_ms=self.duration_ms)

    def describe(self) -> str:
        return f'Long-press "{self.target}" ({self.duration_ms}ms)'


class BackAction(Action):
    """Press the back/navigate-up button."""

    def execute(self, device: Any) -> dict:
        return device.back()

    def describe(self) -> str:
        return "Press back"


class HomeAction(Action):
    """Return to the home screen."""

    def execute(self, device: Any) -> dict:
        return device.go_home()

    def describe(self) -> str:
        return "Go home"


class BurstAction(Action):
    """Execute multiple actions back-to-back without observation between them.

    Use this for testing race conditions (e.g. rapid double-tap) where
    the interesting bug only appears when actions fire faster than the
    normal observe-act cycle allows.

    Args:
        actions: Ordered list of actions to execute in rapid succession.
    """

    def __init__(self, actions: list[Action]) -> None:
        self._actions = actions

    def execute(self, device: Any) -> dict:
        """Execute all contained actions sequentially without delays.

        Args:
            device: A revyl DeviceClient instance.

        Returns:
            Response dict from the last action.
        """
        result: dict = {}
        for action in self._actions:
            result = action.execute(device)
        return result

    def describe(self) -> str:
        descs = [a.describe() for a in self._actions]
        return "Burst[" + " -> ".join(descs) + "]"


ActionGeneratorFn = Callable[[Any, dict[str, Any]], list[Action]]

_GENERATOR_REGISTRY: list[ActionGeneratorFn] = []


def action_generator(fn: ActionGeneratorFn) -> ActionGeneratorFn:
    """Decorator that registers a function as an action generator.

    The function receives (device, extractor_values) and returns a list
    of possible actions for the current screen state.

    Args:
        fn: A callable (device, state) -> list[Action].

    Returns:
        The original function, now registered.
    """
    _GENERATOR_REGISTRY.append(fn)
    return fn


def get_all_generators() -> list[ActionGeneratorFn]:
    """Return all registered action generators."""
    return list(_GENERATOR_REGISTRY)


def clear_generator_registry() -> None:
    """Clear the global action generator registry."""
    _GENERATOR_REGISTRY.clear()


class WeightedGenerators:
    """Probability-weighted collection of action generators.

    Higher-weight generators are more likely to be selected during
    autonomous exploration.

    Attributes:
        entries: List of (weight, generator) tuples.
    """

    def __init__(self, entries: list[tuple[int, ActionGeneratorFn]]) -> None:
        self.entries = entries

    def pick_action(self, device: Any, state: dict[str, Any]) -> Optional[Action]:
        """Select a random action from weighted generators.

        Evaluates all generators, collects candidate actions with their
        weights, then picks one randomly based on weight distribution.

        Args:
            device: A revyl DeviceClient instance.
            state: Current extractor values dict.

        Returns:
            A randomly selected Action, or None if no actions are available.
        """
        candidates: list[tuple[int, Action]] = []

        for weight, gen in self.entries:
            try:
                actions = gen(device, state)
                for action in actions:
                    candidates.append((weight, action))
            except Exception:
                continue

        if not candidates:
            return None

        weights = [w for w, _ in candidates]
        chosen = random.choices(candidates, weights=weights, k=1)[0]
        return chosen[1]


def weighted(entries: list[tuple[int, ActionGeneratorFn]]) -> WeightedGenerators:
    """Create a weighted collection of action generators.

    Higher weights mean higher probability of selection during exploration.

    Args:
        entries: List of (weight, generator_fn) tuples.

    Returns:
        A WeightedGenerators instance.

    Example::

        actions = weighted([
            (10, tap_buttons),   # 10x more likely
            (3, scroll_content),
            (1, type_random),
        ])
    """
    return WeightedGenerators(entries)
