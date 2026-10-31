import json
from dataclasses import dataclass
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_DIR / "config.json"


@dataclass
class AppState:
    model_path: str
    model_name: str

    def resolved_model_path(self):
        # type: () -> Path
        """model_path as an absolute path (relative paths are relative to the project)."""
        p = Path(self.model_path)
        return p if p.is_absolute() else PROJECT_DIR / p

    def model_exists(self):
        # type: () -> bool
        return bool(self.model_path) and self.resolved_model_path().is_dir()

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
