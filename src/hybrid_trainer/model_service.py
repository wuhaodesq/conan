from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path


@dataclass(slots=True)
class ModelServiceConfig:
    name: str
    role: str
    command: str
    timeout_seconds: int
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "role": self.role,
            "command": self.command,
            "timeout_seconds": self.timeout_seconds,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "ModelServiceConfig":
        command = payload["command"]
        if isinstance(command, list):
            command = json.dumps([str(item) for item in command], ensure_ascii=False)

        return cls(
            name=str(payload["name"]),
            role=str(payload["role"]),
            command=str(command),
            timeout_seconds=int(payload.get("timeout_seconds", 30)),
            metadata=dict(payload.get("metadata", {})),
        )


@dataclass
class ModelServiceRegistry:
    services: dict[str, ModelServiceConfig] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: str) -> "ModelServiceRegistry":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        items = payload.get("services", payload)
        registry = cls()
        for item in items:
            service = ModelServiceConfig.from_dict(item)
            registry.services[service.name] = service
        return registry

    def resolve(self, name: str, role: str | None = None) -> ModelServiceConfig:
        if name not in self.services:
            raise KeyError(f"Unknown model service: {name}")
        service = self.services[name]
        if role and service.role != role:
            raise ValueError(f"Service {name} has role {service.role}, expected {role}")
        return service
