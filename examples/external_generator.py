from __future__ import annotations

import json
import sys


def main() -> None:
    payload = json.load(sys.stdin)
    iteration = int(payload.get("iteration", 1))
    print(
        json.dumps(
            {
                "task": {
                    "task_id": f"generated-{iteration}",
                    "prompt": f"Solve generated task {iteration}",
                    "candidate_answer": str(iteration * 2),
                    "reference_answer": str(iteration * 2),
                }
            }
        )
    )


if __name__ == "__main__":
    main()
