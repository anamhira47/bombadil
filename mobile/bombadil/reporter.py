"""Rich terminal reporter for demo-worthy live output.

Provides real-time property status, action logging, violation alerts,
and a final summary table with session recording URL.
"""

from __future__ import annotations

from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from bombadil.properties import PropertyStatus, Violation


class BombadilReporter:
    """Rich terminal reporter for Bombadil Mobile exploration runs.

    Outputs real-time step progress, property checks, actions taken,
    and a final summary suitable for live demos.

    Attributes:
        console: Rich Console instance for output.
        verbose: Whether to show extraction details.
    """

    def __init__(self, verbose: bool = True) -> None:
        self.console = Console()
        self.verbose = verbose
        self._violations: list[Violation] = []

    def on_start(self, platform: str, max_steps: int, num_properties: int) -> None:
        """Print the exploration header.

        Args:
            platform: Target platform (ios/android).
            max_steps: Maximum exploration steps configured.
            num_properties: Number of properties being checked.
        """
        self.console.print()
        self.console.print(
            Panel(
                f"[bold]Bombadil Mobile[/bold] -- Property-Based Testing\n\n"
                f"Platform: [cyan]{platform}[/cyan]  |  "
                f"Max steps: [cyan]{max_steps}[/cyan]  |  "
                f"Properties: [cyan]{num_properties}[/cyan]",
                title="[bold blue]Tom Bombadil[/bold blue]",
                border_style="blue",
            )
        )
        self.console.print()

    def on_viewer_url(self, url: str) -> None:
        """Print the live viewer URL prominently.

        Args:
            url: The Revyl viewer URL for the device session.
        """
        self.console.print(f"  [bold green]Live viewer:[/bold green] {url}")
        self.console.print()

    def on_step_start(self, step: int, total: int) -> None:
        """Mark the start of a new exploration step.

        Args:
            step: Current step number (1-based).
            total: Total maximum steps.
        """
        self.console.rule(f"[dim]Step {step}/{total}[/dim]", style="dim")

    def on_extraction(self, name: str, value: object) -> None:
        """Log an extractor result.

        Args:
            name: Extractor name.
            value: Extracted value.
        """
        if self.verbose:
            self.console.print(f"  [dim]extract:[/dim] {name} = [yellow]{value}[/yellow]")

    def on_property_check(self, name: str, status: PropertyStatus) -> None:
        """Show property check result with a colored indicator.

        Args:
            name: Property name.
            status: Evaluation result.
        """
        icons = {
            PropertyStatus.HOLDING: "[green]PASS[/green]",
            PropertyStatus.VIOLATED: "[bold red]FAIL[/bold red]",
            PropertyStatus.PENDING: "[yellow]PEND[/yellow]",
        }
        self.console.print(f"  {icons[status]}  {name}")

    def on_action(self, description: str) -> None:
        """Log the action taken in this step.

        Args:
            description: Human-readable action description.
        """
        self.console.print(f"  [bold cyan]action:[/bold cyan] {description}")

    def on_violation(self, violation: Violation) -> None:
        """Alert on a property violation with details.

        Args:
            violation: The violation record.
        """
        self._violations.append(violation)
        self.console.print()
        self.console.print(
            Panel(
                f"[bold red]VIOLATION[/bold red] at step {violation.step}\n\n"
                f"Property: [bold]{violation.property_name}[/bold]\n"
                f"Message: {violation.message}"
                + (f"\nScreenshot: {violation.screenshot_path}" if violation.screenshot_path else ""),
                border_style="red",
            )
        )
        self.console.print()

    def on_error(self, step: int, error: str) -> None:
        """Log a non-fatal error during exploration.

        Args:
            step: Step at which the error occurred.
            error: Error message.
        """
        self.console.print(f"  [red]error at step {step}:[/red] {error}")

    def on_complete(
        self,
        total_steps: int,
        violations: list[Violation],
        duration_seconds: float,
        report_url: Optional[str] = None,
    ) -> None:
        """Print the final summary table.

        Args:
            total_steps: Total steps executed.
            violations: All violations found.
            duration_seconds: Total run duration.
            report_url: Revyl session report URL, if available.
        """
        self.console.print()
        self.console.rule("[bold]Exploration Complete[/bold]")
        self.console.print()

        table = Table(title="Summary", show_header=False, border_style="blue")
        table.add_column("Metric", style="bold")
        table.add_column("Value")

        table.add_row("Steps executed", str(total_steps))
        table.add_row("Duration", f"{duration_seconds:.1f}s")

        if violations:
            table.add_row("Violations", f"[bold red]{len(violations)}[/bold red]")
            for v in violations:
                table.add_row("", f"  [red]{v.property_name}[/red]: {v.message}")
        else:
            table.add_row("Violations", "[bold green]0[/bold green]")

        if report_url:
            table.add_row("Session recording", f"[link={report_url}]{report_url}[/link]")

        self.console.print(table)
        self.console.print()

        if not violations:
            self.console.print("[bold green]All properties held. No bugs found.[/bold green]")
        else:
            self.console.print(
                f"[bold red]{len(violations)} violation(s) found. "
                f"See details above.[/bold red]"
            )
        self.console.print()
