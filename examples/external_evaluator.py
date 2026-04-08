from __future__ import annotations

import json
import sys


def _normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


def main() -> None:
    payload = json.load(sys.stdin)
    task = payload["task"]
    pass_threshold = float(payload.get("pass_threshold", 0.8))
    reference_answer = str(task.get("reference_answer", ""))

    if reference_answer:
        score = 1.0 if _normalize(str(task.get("candidate_answer", ""))) == _normalize(reference_answer) else 0.0
    else:
        prompt = str(task.get("prompt", ""))
        candidate = str(task.get("candidate_answer", ""))
        score = min(1.0, len(candidate) / max(len(prompt), 1))

    print(
        json.dumps(
            {
                "task_id": task["task_id"],
                "score": score,
                "passed": score >= pass_threshold,
            }
        )
    )


if __name__ == "__main__":
    main()
