import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CREDENTIAL_NAMES = {"TAVILY_API_KEY", "TINYFISH_API_KEY", "HUNTER_API_KEY", "APOLLO_API_KEY", "JSONBIN_MASTER_KEY", "JSONBIN_COLLECTION_ID", "DASYANTE_STORAGE", "DASYANTE_MAX_COMPANIES_PER_REQUEST"}


def load_environment(path: str | Path | None = None) -> None:
    """Load local credentials without executing shell code; local keys replace stale exports."""
    env_path = Path(path or os.environ.get("DASYANTE_ENV_FILE", "") or PROJECT_ROOT / ".env")
    if not env_path.exists():
        return
    values: dict[str, str] = {}
    for number, line in enumerate(env_path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, separator, value = line.partition("=")
        if not separator:
            raise ValueError(f"invalid credential assignment on line {number}")
        name, value = name.strip(), value.strip()
        if name not in CREDENTIAL_NAMES:
            continue
        if value.startswith(("'", '"')):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError(f"invalid quoted credential on line {number}")
            value = value[1:-1]
        values[name] = value
    os.environ.update(values)
