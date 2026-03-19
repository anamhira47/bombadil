"""Core exploration engine -- the autonomous testing loop.

Implements the observe -> extract -> check -> act cycle using the
Revyl DeviceClient for device interaction.
"""

from __future__ import annotations

import os
import random
import time
from typing import Any, Optional

from pydantic import BaseModel, Field
from revyl import DeviceClient, RevylError

from bombadil.actions import Action, WeightedGenerators, get_all_generators
from bombadil.extractors import Extractor, evaluate_all, get_all_extractors
from bombadil.properties import (
    Property,
    PropertyStatus,
    StateSnapshot,
    Violation,
)
from bombadil.reporter import BombadilReporter


class ExplorationConfig(BaseModel):
    """Configuration for an autonomous exploration run.

    Attributes:
        platform: Target platform ("ios" or "android").
        max_steps: Maximum number of explore-act cycles.
        settle_time_ms: Milliseconds to wait after each action for UI to settle.
        exit_on_first_violation: Stop immediately when a violation is found.
        screenshot_on_violation: Save a screenshot when a violation occurs.
        app_url: URL to an .ipa or .apk to install on the device.
        app_id: Revyl app ID to resolve the latest build.
        open_viewer: Open the live viewer in the browser after device start.
        screenshot_dir: Directory to save violation screenshots.
    """

    platform: str = "ios"
    max_steps: int = 30
    settle_time_ms: int = 1000
    exit_on_first_violation: bool = False
    screenshot_on_violation: bool = True
    app_url: Optional[str] = None
    app_id: Optional[str] = None
    open_viewer: bool = True
    screenshot_dir: str = "screenshots"


class ExplorationResult(BaseModel):
    """Outcome of an autonomous exploration run.

    Attributes:
        total_steps: Number of steps actually executed.
        violations: All property violations detected.
        properties_checked: Number of properties evaluated per step.
        actions_taken: Descriptions of all actions taken.
        session_report_url: Revyl session report URL with recording.
        duration_seconds: Wall-clock duration of the run.
    """

    total_steps: int
    violations: list[Violation] = Field(default_factory=list)
    properties_checked: int = 0
    actions_taken: list[str] = Field(default_factory=list)
    session_report_url: Optional[str] = None
    duration_seconds: float = 0.0


class ExplorationEngine:
    """Autonomous mobile UI explorer with property checking.

    Runs the core Bombadil loop: observe screen state via AI extractors,
    check temporal properties, pick a random weighted action, execute it,
    and repeat.

    Args:
        properties: Temporal properties to check on every step.
        action_source: A WeightedGenerators instance or None to use registered generators.
        extractors: Specific extractors to evaluate, or None for all registered.
        config: Exploration configuration.
        reporter: Terminal reporter for live output.
    """

    def __init__(
        self,
        properties: list[Property],
        action_source: Optional[WeightedGenerators] = None,
        extractors: Optional[list[Extractor]] = None,
        config: Optional[ExplorationConfig] = None,
        reporter: Optional[BombadilReporter] = None,
    ) -> None:
        self.properties = properties
        self.action_source = action_source
        self.extractors = extractors or get_all_extractors()
        self.config = config or ExplorationConfig()
        self.reporter = reporter or BombadilReporter()
        self._history: list[StateSnapshot] = []

    def run(self) -> ExplorationResult:
        """Execute the full autonomous exploration loop.

        Starts a device session, runs up to ``max_steps`` exploration
        cycles, checks all properties, and returns the result.

        Returns:
            ExplorationResult with violations, actions, and session URL.
        """
        start_time = time.time()
        violations: list[Violation] = []
        actions_taken: list[str] = []
        report_url: Optional[str] = None

        self.reporter.on_start(
            platform=self.config.platform,
            max_steps=self.config.max_steps,
            num_properties=len(self.properties),
        )

        start_kwargs: dict[str, Any] = {
            "platform": self.config.platform,
            "open_viewer": self.config.open_viewer,
        }
        if self.config.app_url:
            start_kwargs["app_url"] = self.config.app_url
        if self.config.app_id:
            start_kwargs["app_id"] = self.config.app_id

        try:
            with DeviceClient.start(**start_kwargs) as device:
                try:
                    info = device.info()
                    viewer_url = info.get("viewer_url", "")
                    if viewer_url:
                        self.reporter.on_viewer_url(viewer_url)
                except Exception:
                    pass

                for step in range(1, self.config.max_steps + 1):
                    self.reporter.on_step_start(step, self.config.max_steps)

                    try:
                        device.screenshot()
                    except RevylError as e:
                        self.reporter.on_error(step, f"Screenshot failed: {e}")
                        continue

                    state = evaluate_all(device, self.extractors)
                    for name, value in state.items():
                        self.reporter.on_extraction(name, value)

                    snapshot = StateSnapshot(
                        timestamp=time.time(), step=step, values=state
                    )
                    self._history.append(snapshot)

                    step_violations = self._check_properties(step, device=device, state=state)
                    violations.extend(step_violations)

                    if step_violations and self.config.exit_on_first_violation:
                        break

                    action = self._pick_action(device, state)
                    if action:
                        try:
                            action.execute(device)
                            desc = action.describe()
                            actions_taken.append(desc)
                            self.reporter.on_action(desc)
                        except RevylError as e:
                            self.reporter.on_error(step, f"Action failed: {e}")

                    if self.config.settle_time_ms > 0:
                        time.sleep(self.config.settle_time_ms / 1000.0)

                try:
                    report = device.wait_for_report(timeout=15)
                    report_url = report.get("report_url")
                except Exception:
                    pass

        except RevylError as e:
            self.reporter.on_error(0, f"Device session failed: {e}")

        duration = time.time() - start_time
        self.reporter.on_complete(
            total_steps=len(actions_taken),
            violations=violations,
            duration_seconds=duration,
            report_url=report_url,
        )

        return ExplorationResult(
            total_steps=len(actions_taken),
            violations=violations,
            properties_checked=len(self.properties),
            actions_taken=actions_taken,
            session_report_url=report_url,
            duration_seconds=duration,
        )

    def _check_properties(
        self, step: int, device: Any | None = None, state: dict[str, Any] | None = None
    ) -> list[Violation]:
        """Evaluate all properties against current state history.

        Args:
            step: Current exploration step number.
            device: Active DeviceClient for violation screenshots.
            state: Current extractor values for contextual violation messages.

        Returns:
            List of any new violations detected this step.
        """
        violations: list[Violation] = []
        for prop in self.properties:
            status = prop.evaluate(self._history)
            self.reporter.on_property_check(prop.name, status)

            if status == PropertyStatus.VIOLATED:
                context = self._build_violation_context(state or {})
                screenshot_path = self._save_violation_screenshot(device, step, prop.name)

                violation = Violation(
                    property_name=prop.name,
                    timestamp=time.time(),
                    step=step,
                    message=f"Property '{prop.name}' violated at step {step}. {context}",
                    screenshot_path=screenshot_path,
                )
                violations.append(violation)
                self.reporter.on_violation(violation)

        return violations

    def _build_violation_context(self, state: dict[str, Any]) -> str:
        """Build a human-readable summary of extractor values for violation messages.

        Args:
            state: Current extractor name-value mapping.

        Returns:
            Formatted string like "cart_count=0, price=0.00".
        """
        if not state:
            return ""
        pairs = [f"{k}={v}" for k, v in state.items()]
        return "State: " + ", ".join(pairs)

    def _save_violation_screenshot(
        self, device: Any | None, step: int, property_name: str
    ) -> str | None:
        """Save a screenshot when a violation occurs, if configured.

        Args:
            device: Active DeviceClient.
            step: Step number for the filename.
            property_name: Property name for the filename.

        Returns:
            Path to the saved screenshot, or None if saving failed or is disabled.
        """
        if not self.config.screenshot_on_violation or device is None:
            return None
        try:
            os.makedirs(self.config.screenshot_dir, exist_ok=True)
            safe_name = property_name.replace(" ", "_").replace("/", "_")[:40]
            path = os.path.join(self.config.screenshot_dir, f"violation_step{step}_{safe_name}.png")
            device.screenshot(out=path)
            return path
        except Exception:
            return None

    def _pick_action(self, device: Any, state: dict[str, Any]) -> Optional[Action]:
        """Select the next action to take.

        Uses the weighted action source if provided, otherwise falls back
        to iterating through registered generators.

        Args:
            device: Active DeviceClient.
            state: Current extractor values.

        Returns:
            An Action to execute, or None if no actions are available.
        """
        if self.action_source:
            return self.action_source.pick_action(device, state)

        for gen in get_all_generators():
            try:
                actions = gen(device, state)
                if actions:
                    return random.choice(actions)
            except Exception:
                continue

        return None
