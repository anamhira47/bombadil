#!/usr/bin/env python3
"""CLI entry point for Bombadil Mobile exploration runs.

Usage::

    python run.py --platform ios specs/defaults.py
    python run.py --platform ios --app-url https://... --max-steps 50 specs/ecommerce.py
    python run.py --platform ios --app-id abc123 --exit-on-violation specs/defaults.py
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

from bombadil.actions import WeightedGenerators
from bombadil.engine import ExplorationConfig, ExplorationEngine
from bombadil.extractors import Extractor, clear_registry
from bombadil.properties import Property
from bombadil.reporter import BombadilReporter


def load_spec(spec_path: str) -> tuple[list[Property], list[Extractor], WeightedGenerators | None]:
    """Dynamically load a spec module and collect its properties, extractors, and actions.

    Args:
        spec_path: Path to the spec Python file.

    Returns:
        Tuple of (properties, extractors, weighted_actions_or_none).

    Raises:
        SystemExit: If the spec file cannot be loaded or contains no properties.
    """
    path = Path(spec_path).resolve()
    if not path.exists():
        print(f"Error: spec file not found: {spec_path}")
        sys.exit(1)

    clear_registry()

    spec = importlib.util.spec_from_file_location("spec", path)
    if spec is None or spec.loader is None:
        print(f"Error: cannot load spec: {spec_path}")
        sys.exit(1)

    module = importlib.util.module_from_spec(spec)
    sys.modules["spec"] = module
    spec.loader.exec_module(module)

    properties: list[Property] = []
    extractors: list[Extractor] = []
    actions: WeightedGenerators | None = None

    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if isinstance(attr, Property):
            properties.append(attr)
        elif isinstance(attr, Extractor):
            extractors.append(attr)
        elif isinstance(attr, WeightedGenerators):
            actions = attr
        elif isinstance(attr, list):
            for item in attr:
                if isinstance(item, Property):
                    properties.append(item)
                elif isinstance(item, Extractor):
                    extractors.append(item)

    seen_names: set[str] = set()
    unique_props = []
    for p in properties:
        if p.name not in seen_names:
            seen_names.add(p.name)
            unique_props.append(p)
    properties = unique_props

    if not properties:
        print(f"Warning: no properties found in {spec_path}")

    return properties, extractors, actions


def main() -> None:
    """Parse CLI arguments and run the exploration engine."""
    parser = argparse.ArgumentParser(
        description="Bombadil Mobile -- property-based testing for mobile UIs"
    )
    parser.add_argument("spec", help="Path to the spec file (e.g. specs/defaults.py)")
    parser.add_argument("--platform", default="ios", choices=["ios", "android"])
    parser.add_argument("--app-url", help="URL to .ipa or .apk to install")
    parser.add_argument("--app-id", help="Revyl app ID to resolve latest build")
    parser.add_argument("--max-steps", type=int, default=30)
    parser.add_argument("--settle-ms", type=int, default=1000)
    parser.add_argument("--exit-on-violation", action="store_true")
    parser.add_argument("--no-viewer", action="store_true", help="Don't open the live viewer")
    parser.add_argument("--quiet", action="store_true", help="Minimal output")

    args = parser.parse_args()

    properties, extractors, actions = load_spec(args.spec)

    config = ExplorationConfig(
        platform=args.platform,
        max_steps=args.max_steps,
        settle_time_ms=args.settle_ms,
        exit_on_first_violation=args.exit_on_violation,
        app_url=args.app_url,
        app_id=args.app_id,
        open_viewer=not args.no_viewer,
    )

    reporter = BombadilReporter(verbose=not args.quiet)

    engine = ExplorationEngine(
        properties=properties,
        action_source=actions,
        extractors=extractors if extractors else None,
        config=config,
        reporter=reporter,
    )

    result = engine.run()
    sys.exit(1 if result.violations else 0)


if __name__ == "__main__":
    main()
