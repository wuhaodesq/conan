from __future__ import annotations

import json
import os
import shlex
import subprocess


class CommandBackendError(RuntimeError):
    """Raised when an external command backend cannot return a valid JSON response."""


def parse_command(command: str) -> list[str]:
    text = command.strip()
    if not text:
        raise CommandBackendError("external command must not be empty")

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = None

    if isinstance(payload, list) and payload and all(isinstance(item, str) for item in payload):
        return payload

    return shlex.split(text, posix=os.name != "nt")


def run_json_command(command: str, payload: dict, timeout_seconds: int) -> dict:
    try:
        completed = subprocess.run(
            parse_command(command),
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise CommandBackendError(
            f"external command timed out after {timeout_seconds}s: {_summarize_command(command)}"
        ) from exc
    except OSError as exc:
        raise CommandBackendError(
            f"external command failed to start: {_summarize_command(command)}"
        ) from exc

    stdout = completed.stdout.strip()
    if completed.returncode != 0:
        raise CommandBackendError(
            "external command exited with "
            f"{completed.returncode}: {_summarize_command(command)}"
            f" | stderr={_summarize_stream(completed.stderr)}"
        )

    if not stdout:
        raise CommandBackendError(
            f"external command produced no JSON output: {_summarize_command(command)}"
        )

    try:
        response = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise CommandBackendError(
            "external command returned invalid JSON: "
            f"{_summarize_command(command)} | stdout={_summarize_stream(stdout)}"
        ) from exc

    if not isinstance(response, dict):
        raise CommandBackendError(
            f"external command must return a JSON object: {_summarize_command(command)}"
        )
    return response


def _summarize_command(command: str) -> str:
    return " ".join(parse_command(command))


def _summarize_stream(text: str) -> str:
    compact = " ".join(text.strip().split())
    if len(compact) <= 160:
        return compact
    return compact[:157] + "..."
