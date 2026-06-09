from importlib import import_module
from pathlib import Path
import runpy


def load_config(config_name):
    """Load a launcher config from JazLabs.launchers.configs or a Python file."""
    if config_name.endswith(".py") or any(sep in config_name for sep in ("/", "\\")):
        path = Path(config_name).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        return runpy.run_path(str(path))

    module = import_module(f"JazLabs.launchers.configs.{config_name}")
    return vars(module)


def get_named_config(config, collection_name, item_name):
    items = config.get(collection_name, [])
    for item in items:
        if item.get("name") == item_name:
            return dict(item)
    names = ", ".join(item.get("name", "<unnamed>") for item in items)
    raise ValueError(f"No {collection_name} entry named {item_name!r}. Available: {names}")


def merge_overrides(base, overrides):
    merged = dict(base)
    for key, value in overrides.items():
        if value is not None:
            merged[key] = value
    return merged

