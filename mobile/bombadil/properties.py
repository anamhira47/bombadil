"""Temporal property DSL mirroring Bombadil web's LTL operators.

Provides ``always``, ``eventually``, ``now``, and ``next_state`` -- the same
operators used in web Bombadil's TypeScript API, expressed in Python.

Example::

    from bombadil import extract, always, eventually, now

    error_visible = extract("Is there an error dialog visible?", returns=bool)
    loading = extract("Is a loading spinner visible?", returns=bool)

    no_crashes = always(lambda: not error_visible.current)
    loading_resolves = always(
        now(lambda: loading.current).implies(
            eventually(lambda: not loading.current).within(seconds=10)
        )
    )
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Callable, Optional

from pydantic import BaseModel


class PropertyStatus(str, Enum):
    """Evaluation result for a single property check."""

    HOLDING = "holding"
    VIOLATED = "violated"
    PENDING = "pending"


class Violation(BaseModel):
    """Record of a property violation observed during exploration.

    Attributes:
        property_name: Human-readable name of the violated property.
        timestamp: Unix timestamp when the violation was detected.
        step: Exploration step number at which the violation occurred.
        message: Descriptive message explaining the violation.
        screenshot_path: Path to the screenshot captured at violation time, if any.
    """

    property_name: str
    timestamp: float
    step: int
    message: str
    screenshot_path: Optional[str] = None


class StateSnapshot(BaseModel):
    """Frozen observation of all extractor values at a point in time.

    Attributes:
        timestamp: Unix timestamp when the snapshot was captured.
        step: Exploration step number.
        values: Mapping of extractor names to their observed values.
    """

    timestamp: float
    step: int
    values: dict[str, object]


class Property:
    """Base class for all temporal properties.

    Subclasses implement :meth:`evaluate` to check the property against
    a rolling window of state snapshots.

    Attributes:
        name: Human-readable property name for reporting.
    """

    def __init__(self, name: str = "unnamed") -> None:
        self.name = name

    def evaluate(self, history: list[StateSnapshot]) -> PropertyStatus:
        """Check this property against the observed state history.

        Args:
            history: Ordered list of all state snapshots captured so far.

        Returns:
            Current status of the property.

        Raises:
            NotImplementedError: If the subclass has not implemented evaluation.
        """
        raise NotImplementedError

    def implies(self, consequent: Property) -> Property:
        """Logical implication: if self holds then consequent must hold.

        Args:
            consequent: The property that must hold when self holds.

        Returns:
            A new ImpliesProperty.
        """
        return _ImpliesProperty(antecedent=self, consequent=consequent)

    def and_(self, other: Property) -> Property:
        """Logical conjunction: both self and other must hold.

        Args:
            other: The other property to conjoin.

        Returns:
            A new AndProperty.
        """
        return _AndProperty(left=self, right=other)

    def or_(self, other: Property) -> Property:
        """Logical disjunction: at least one must hold.

        Args:
            other: The other property.

        Returns:
            A new OrProperty.
        """
        return _OrProperty(left=self, right=other)

    def not_(self) -> Property:
        """Logical negation of this property.

        Returns:
            A new NotProperty.
        """
        return _NotProperty(inner=self)


class _AlwaysProperty(Property):
    """Invariant: the predicate must hold in every observed state."""

    def __init__(self, predicate: Callable[[], bool] | Property, name: str = "always") -> None:
        super().__init__(name=name)
        self._predicate = predicate

    def evaluate(self, history: list[StateSnapshot]) -> PropertyStatus:
        if not history:
            return PropertyStatus.HOLDING
        if isinstance(self._predicate, Property):
            return self._predicate.evaluate(history)
        try:
            return PropertyStatus.HOLDING if self._predicate() else PropertyStatus.VIOLATED
        except Exception:
            return PropertyStatus.VIOLATED


class EventuallyProperty(Property):
    """Guarantee: the predicate must become true within a time window.

    Use :meth:`within` to set the deadline.
    """

    def __init__(self, predicate: Callable[[], bool], name: str = "eventually") -> None:
        super().__init__(name=name)
        self._predicate = predicate
        self._deadline_seconds: Optional[float] = None
        self._first_relevant_time: Optional[float] = None

    def within(self, seconds: float) -> EventuallyProperty:
        """Set the time window in which the predicate must become true.

        Args:
            seconds: Maximum seconds to wait for the predicate.

        Returns:
            Self, for chaining.
        """
        self._deadline_seconds = seconds
        return self

    def mark_relevant(self, timestamp: float) -> None:
        """Record when this eventually-property became relevant.

        Args:
            timestamp: Unix timestamp when relevance started.
        """
        if self._first_relevant_time is None:
            self._first_relevant_time = timestamp

    def reset(self) -> None:
        """Clear the relevance tracker for re-use across cycles."""
        self._first_relevant_time = None

    def evaluate(self, history: list[StateSnapshot]) -> PropertyStatus:
        try:
            result = self._predicate()
        except Exception:
            result = False

        if result:
            self.reset()
            return PropertyStatus.HOLDING

        if self._deadline_seconds is None or self._first_relevant_time is None:
            return PropertyStatus.PENDING

        elapsed = time.time() - self._first_relevant_time
        return PropertyStatus.VIOLATED if elapsed > self._deadline_seconds else PropertyStatus.PENDING


class _NowProperty(Property):
    """Snapshot property: the predicate must hold in the current state."""

    def __init__(self, predicate: Callable[[], bool] | Property, name: str = "now") -> None:
        super().__init__(name=name)
        self._predicate = predicate

    def evaluate(self, history: list[StateSnapshot]) -> PropertyStatus:
        if not history:
            return PropertyStatus.HOLDING
        if isinstance(self._predicate, Property):
            return self._predicate.evaluate(history)
        try:
            return PropertyStatus.HOLDING if self._predicate() else PropertyStatus.VIOLATED
        except Exception:
            return PropertyStatus.VIOLATED


class _NextStateProperty(Property):
    """Transition property: predicate must hold in the next observed state.

    Auto-arms on first evaluation and checks the predicate on the
    subsequent step. Re-arms after each check so it continuously
    validates state transitions.
    """

    def __init__(self, predicate: Callable[[], bool], name: str = "next_state") -> None:
        super().__init__(name=name)
        self._predicate = predicate
        self._armed_at_step: Optional[int] = None

    def evaluate(self, history: list[StateSnapshot]) -> PropertyStatus:
        """Check predicate on the step after arming, then re-arm.

        Args:
            history: Ordered state snapshots.

        Returns:
            PENDING on first call or right after arming, HOLDING or
            VIOLATED once the next step arrives.
        """
        if not history:
            return PropertyStatus.PENDING

        current_step = history[-1].step

        if self._armed_at_step is None:
            self._armed_at_step = current_step
            return PropertyStatus.PENDING

        if current_step <= self._armed_at_step:
            return PropertyStatus.PENDING

        try:
            result = self._predicate()
        except Exception:
            result = False

        self._armed_at_step = current_step
        return PropertyStatus.HOLDING if result else PropertyStatus.VIOLATED


class _ImpliesProperty(Property):
    """Logical implication: antecedent holding requires consequent to hold."""

    def __init__(self, antecedent: Property, consequent: Property) -> None:
        super().__init__(name=f"{antecedent.name} => {consequent.name}")
        self._antecedent = antecedent
        self._consequent = consequent

    def evaluate(self, history: list[StateSnapshot]) -> PropertyStatus:
        if self._antecedent.evaluate(history) != PropertyStatus.HOLDING:
            return PropertyStatus.HOLDING
        if isinstance(self._consequent, EventuallyProperty) and history:
            self._consequent.mark_relevant(history[-1].timestamp)
        status = self._consequent.evaluate(history)
        if status == PropertyStatus.VIOLATED:
            return PropertyStatus.VIOLATED
        return PropertyStatus.PENDING if status == PropertyStatus.PENDING else PropertyStatus.HOLDING


class _AndProperty(Property):
    def __init__(self, left: Property, right: Property) -> None:
        super().__init__(name=f"({left.name} AND {right.name})")
        self._left, self._right = left, right

    def evaluate(self, history: list[StateSnapshot]) -> PropertyStatus:
        l, r = self._left.evaluate(history), self._right.evaluate(history)
        if l == PropertyStatus.VIOLATED or r == PropertyStatus.VIOLATED:
            return PropertyStatus.VIOLATED
        if l == PropertyStatus.PENDING or r == PropertyStatus.PENDING:
            return PropertyStatus.PENDING
        return PropertyStatus.HOLDING


class _OrProperty(Property):
    def __init__(self, left: Property, right: Property) -> None:
        super().__init__(name=f"({left.name} OR {right.name})")
        self._left, self._right = left, right

    def evaluate(self, history: list[StateSnapshot]) -> PropertyStatus:
        l, r = self._left.evaluate(history), self._right.evaluate(history)
        if l == PropertyStatus.HOLDING or r == PropertyStatus.HOLDING:
            return PropertyStatus.HOLDING
        if l == PropertyStatus.PENDING or r == PropertyStatus.PENDING:
            return PropertyStatus.PENDING
        return PropertyStatus.VIOLATED


class _NotProperty(Property):
    def __init__(self, inner: Property) -> None:
        super().__init__(name=f"NOT({inner.name})")
        self._inner = inner

    def evaluate(self, history: list[StateSnapshot]) -> PropertyStatus:
        s = self._inner.evaluate(history)
        if s == PropertyStatus.HOLDING:
            return PropertyStatus.VIOLATED
        return PropertyStatus.HOLDING if s == PropertyStatus.VIOLATED else PropertyStatus.PENDING


def _derive_name(predicate: Callable | Property, prefix: str) -> str:
    if isinstance(predicate, Property):
        return f"{prefix}({predicate.name})"
    fn_name = getattr(predicate, "__name__", None) or getattr(predicate, "__qualname__", "")
    if fn_name and fn_name != "<lambda>":
        return f"{prefix}({fn_name})"
    return prefix


def always(predicate: Callable[[], bool] | Property, *, name: str = "") -> _AlwaysProperty:
    """Create an invariant property that must hold in every observed state.

    Args:
        predicate: A zero-arg callable returning bool, or a Property.
        name: Optional human-readable name for reporting.

    Returns:
        An AlwaysProperty instance.
    """
    return _AlwaysProperty(predicate, name=name or _derive_name(predicate, "always"))


def eventually(predicate: Callable[[], bool], *, name: str = "") -> EventuallyProperty:
    """Create a guarantee property that must become true within a deadline.

    Chain with ``.within(seconds=N)`` to set the time window.

    Args:
        predicate: A zero-arg callable returning bool.
        name: Optional human-readable name for reporting.

    Returns:
        An EventuallyProperty instance.
    """
    return EventuallyProperty(predicate, name=name or _derive_name(predicate, "eventually"))


def now(predicate: Callable[[], bool] | Property, *, name: str = "") -> _NowProperty:
    """Create a snapshot property that must hold in the current state.

    Args:
        predicate: A zero-arg callable returning bool, or a Property.
        name: Optional human-readable name for reporting.

    Returns:
        A NowProperty instance.
    """
    return _NowProperty(predicate, name=name or _derive_name(predicate, "now"))


def next_state(predicate: Callable[[], bool], *, name: str = "") -> _NextStateProperty:
    """Create a transition property that must hold in the next observed state.

    Args:
        predicate: A zero-arg callable returning bool.
        name: Optional human-readable name for reporting.

    Returns:
        A NextStateProperty instance.
    """
    return _NextStateProperty(predicate, name=name or _derive_name(predicate, "next_state"))
