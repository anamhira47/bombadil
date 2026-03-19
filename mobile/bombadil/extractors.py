"""AI-vision state extractors using Revyl's device.extract().

Replaces web Bombadil's DOM queries with natural-language questions
answered by AI vision on the device screenshot.

Example::

    from bombadil import extract

    error_visible = extract("Is there an error dialog visible?", returns=bool)
    cart_count = extract("How many items are in the cart badge?", returns=int)

    # After evaluation by the engine:
    if error_visible.current:
        print("Error detected!")
"""

from __future__ import annotations

from typing import Any, Optional, Type

_EXTRACTOR_REGISTRY: list[Extractor] = []


class Extractor:
    """AI-vision state observer that wraps a natural-language question.

    Each extractor holds a question that is sent to ``device.extract()``
    on every exploration step. The AI reads the current screenshot and
    returns an answer, which is coerced to the declared return type.

    Attributes:
        question: The natural-language question to ask about the screen.
        return_type: Expected Python type for the answer (bool, int, float, str).
        name: Short identifier derived from the question.
    """

    def __init__(self, question: str, return_type: Type = str, name: str | None = None) -> None:
        self.question = question
        self.return_type = return_type
        self.name = name or self._derive_name(question)
        self._history: list[Any] = []

    @staticmethod
    def _derive_name(question: str) -> str:
        """Derive a short readable name from a question string.

        Args:
            question: The full natural-language question.

        Returns:
            A snake_case identifier like "error_dialog_visible".
        """
        skip = {"is", "there", "a", "an", "the", "are", "on", "in", "of", "or", "with", "any"}
        words = question.rstrip("?").lower().split()
        meaningful = [w for w in words if w not in skip and len(w) > 1]
        return "_".join(meaningful[:5])

    @property
    def current(self) -> Any:
        """Most recently extracted value, or the type's zero-value if never evaluated."""
        if not self._history:
            return self._default()
        return self._history[-1]

    @property
    def previous(self) -> Any:
        """Value from the prior extraction, or the type's zero-value."""
        if len(self._history) < 2:
            return self._default()
        return self._history[-2]

    @property
    def history(self) -> list[Any]:
        """Full history of all extracted values in order."""
        return list(self._history)

    def update(self, raw_value: Any) -> None:
        """Coerce a raw AI response and append to history.

        Args:
            raw_value: The raw value returned by device.extract().
        """
        self._history.append(self._coerce(raw_value))

    def reset(self) -> None:
        """Clear all history (used between exploration runs)."""
        self._history.clear()

    def _coerce(self, value: Any) -> Any:
        """Best-effort type coercion from AI text to the declared type.

        Args:
            value: Raw value from AI.

        Returns:
            Value coerced to self.return_type.
        """
        if value is None:
            return self._default()

        if self.return_type is bool:
            if isinstance(value, bool):
                return value
            s = str(value).strip().lower()
            return s in ("true", "yes", "1", "visible", "present", "shown")

        if self.return_type is int:
            try:
                cleaned = "".join(c for c in str(value) if c.isdigit() or c == "-")
                return int(cleaned) if cleaned else 0
            except (ValueError, TypeError):
                return 0

        if self.return_type is float:
            try:
                cleaned = "".join(c for c in str(value) if c.isdigit() or c in "-.")
                return float(cleaned) if cleaned else 0.0
            except (ValueError, TypeError):
                return 0.0

        return str(value)

    def _default(self) -> Any:
        """Zero-value for the declared return type."""
        defaults = {bool: False, int: 0, float: 0.0, str: ""}
        return defaults.get(self.return_type, None)


def extract(question: str, returns: Type = str, name: str | None = None) -> Extractor:
    """Create an AI-vision extractor for observing mobile screen state.

    The extractor asks the given question about the device screenshot
    on every exploration step and coerces the answer to the declared type.

    Args:
        question: Natural-language question about what's visible on screen.
        returns: Expected Python type (bool, int, float, str).
        name: Optional short name for reporting. Auto-derived from question if omitted.

    Returns:
        An Extractor instance registered for batch evaluation.
    """
    ext = Extractor(question=question, return_type=returns, name=name)
    _EXTRACTOR_REGISTRY.append(ext)
    return ext


def get_all_extractors() -> list[Extractor]:
    """Return all registered extractors for batch evaluation by the engine."""
    return list(_EXTRACTOR_REGISTRY)


def clear_registry() -> None:
    """Clear the global extractor registry (used between spec loads)."""
    _EXTRACTOR_REGISTRY.clear()


def evaluate_all(device: Any, extractors: Optional[list[Extractor]] = None) -> dict[str, Any]:
    """Run all extractors against the current device screen.

    Calls ``device.extract()`` for each extractor and updates its value.

    Args:
        device: A revyl DeviceClient instance with an active session.
        extractors: Specific extractors to evaluate. Defaults to all registered.

    Returns:
        Mapping of extractor names to their coerced values.
    """
    targets = extractors or _EXTRACTOR_REGISTRY
    results: dict[str, Any] = {}

    for ext in targets:
        try:
            response = device.extract(description=ext.question)
            raw = response.get("extracted_value", response.get("result", ""))
        except Exception:
            raw = ext._default()
        ext.update(raw)
        results[ext.name] = ext.current

    return results
