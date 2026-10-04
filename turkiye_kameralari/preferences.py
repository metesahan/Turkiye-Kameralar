import json

from .config import data_dir

_DEFAULTS = {"theme": "dark", "weather_location": None}
_cache: dict | None = None


def _path():
    return data_dir() / "settings.json"


def load() -> dict:
    global _cache
    if _cache is None:
        _cache = dict(_DEFAULTS)
        try:
            stored = json.loads(_path().read_text(encoding="utf-8"))
            if isinstance(stored, dict):
                _cache.update({k: v for k, v in stored.items() if k in _DEFAULTS})
        except (OSError, ValueError):
            pass
    return _cache


def get(key: str):
    return load().get(key, _DEFAULTS.get(key))


def set_value(key: str, value) -> None:
    prefs = load()
    prefs[key] = value
    try:
        path = _path()
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(prefs, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass
