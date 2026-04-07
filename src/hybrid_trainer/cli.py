from __future__ import annotations

import argparse
import json
from pathlib import Path

from .engine import TrainingEngine
from .pipeline import DecisionNode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run hybrid trainer MVP simulation")
    parser.add_argument("--start", type=int, default=1, help="start iteration")
    parser.add_argument("--end", type=int, default=10, help="end iteration")
    parser.add_argument(
        "--node",
        type=str,
        default=DecisionNode.REWARD_CALIBRATION.value,
        choices=[node.value for node in DecisionNode],
        help="decision node used during simulation",
    )
    parser.add_argument("--output", type=str, default="artifacts/run_summary.json", help="summary output path")
    return parser


def run(args: list[str] | None = None) -> Path:
    parser = build_parser()
    ns = parser.parse_args(args=args)

    engine = TrainingEngine()
    node = DecisionNode(ns.node)
    engine.run_cycles(ns.start, ns.end, node)

    dashboard = engine.generate_dashboard()
    strategy_switch = engine.maybe_switch_strategy()
    curriculum_adv = engine.maybe_advance_curriculum()

    payload = {
        "range": {"start": ns.start, "end": ns.end},
        "node": ns.node,
        "dashboard": dashboard.to_dict(),
        "strategy": {
            "current": engine.strategy_manager.current.value,
            "switched": strategy_switch is not None,
        },
        "curriculum": {
            "stage": engine.curriculum_manager.current_stage.name,
            "advanced": curriculum_adv is not None,
        },
    }

    output = Path(ns.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return output


def main() -> None:
    run()


if __name__ == "__main__":
    main()
