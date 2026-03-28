"""
config_loader.py -- Load and validate YAML configuration files.

Provides load_config(path) which:
  1. Reads the YAML file.
  2. Validates required fields are present with correct types.
  3. Returns the validated config dict.
"""

from pathlib import Path
import yaml


_REQUIRED_TOP_LEVEL = {
    "asset": str,
    "period": list,
    "frequency": str,
}

_REQUIRED_MODULE_SECTIONS = [
    "ingestion",
    "features",
    "filtering",
    "labeling",
    "splitting",
    "feature_selection",
    "modeling",
    "evaluation",
]


def load_config(path: str) -> dict:
    """
    Load and validate a YAML pipeline configuration file.

    Args:
        path: Path to YAML file.

    Returns:
        Validated configuration dictionary.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If configuration is invalid.
    """
    yaml_path = Path(path)

    if not yaml_path.exists():
        _src_dir = Path(__file__).parent.parent.parent.parent
        yaml_path = _src_dir / path
        if not yaml_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: '{path}'\n"
                f"  Searched: {Path(path).resolve()}\n"
                f"  Searched: {yaml_path.resolve()}"
            )

    with open(yaml_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if config is None:
        raise ValueError(
            f"Configuration file is empty or not valid YAML: '{path}'"
        )

    _validate_config(config, path=str(path))
    return config


def _validate_config(config: dict, path: str = "<config>") -> None:
    """Validate the configuration dictionary structure."""
    if not isinstance(config, dict):
        raise ValueError(
            f"Configuration must be a top-level YAML dictionary, "
            f"got: {type(config).__name__}"
        )

    for field, expected_type in _REQUIRED_TOP_LEVEL.items():
        if field not in config:
            raise ValueError(
                f"Required field missing in configuration: '{field}'"
            )
        value = config[field]
        if not isinstance(value, expected_type):
            raise ValueError(
                f"Field '{field}' must be {expected_type.__name__}, "
                f"got {type(value).__name__} (value: {value!r})"
            )

    period = config["period"]
    if len(period) != 2:
        raise ValueError(
            f"Field 'period' must have exactly 2 elements [start, end], "
            f"got {len(period)} element(s)."
        )
    for i, elem in enumerate(period):
        if not isinstance(elem, str):
            raise ValueError(
                f"'period[{i}]' must be a string (e.g., '2021-01-01'), "
                f"got {type(elem).__name__} (value: {elem!r})"
            )

    for section in _REQUIRED_MODULE_SECTIONS:
        if section not in config:
            raise ValueError(
                f"Required module section missing: '{section}'"
            )
        value = config[section]
        if not isinstance(value, dict):
            raise ValueError(
                f"Section '{section}' must be a YAML dictionary, "
                f"got {type(value).__name__} (value: {value!r})"
            )
