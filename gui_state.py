import json
from dataclasses import dataclass
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"


@dataclass
class AppState:
    model_path: str
    model_name: str

    @classmethod
    def load(cls):
        # type: () -> AppState
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text())
            return cls(
                model_path=data.get("model_path", ""),
                model_name=data.get("model_name", "(no model)"),
            )
        return cls(model_path="", model_name="(no model)")

    def save(self):
        # type: () -> None
        CONFIG_PATH.write_text(
            json.dumps({"model_path": self.model_path, "model_name": self.model_name}, indent=2)
        )
