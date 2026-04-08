from __future__ import annotations

import json
import sys


def main() -> None:
    payload = json.load(sys.stdin)
    request = payload["request"]
    metrics = request["metrics"]
    strategy = request["strategy"]

    if strategy == "rl":
        objective = "policy_optimization"
        training_steps = max(metrics["total"], 1) * 40
        epochs = 3
    elif strategy == "dpo":
        objective = "preference_optimization"
        training_steps = max(metrics["approve"] + metrics["review"], 1) * 30
        epochs = 2
    else:
        objective = "supervised_finetuning"
        training_steps = max(metrics["approve"] + metrics["review"], 1) * 25
        epochs = 2

    print(
        json.dumps(
            {
                "strategy": strategy,
                "status": "completed",
                "objective": objective,
                "input_samples": max(metrics["total"], 1),
                "training_steps": training_steps,
                "epochs": epochs,
                "curriculum_stage": request["curriculum_stage"],
                "policy_version": request["policy_version"],
                "artifact_path": f"external://trainer/{strategy}",
            }
        )
    )


if __name__ == "__main__":
    main()
