"""Reading the files in config/: TOML for settings, CSV for the cast table.

Every file is meant to be edited by hand, so a mistake is reported with the file and the row
or key, and what is allowed there.
"""
from __future__ import annotations

import csv
import tomllib
from functools import lru_cache
from pathlib import Path

CONFIG = Path(__file__).resolve().parent.parent / "config"

VOICES = ("narrator", "female", "male", "group", "female_group", "divine")
CAST_FILE = "cast.csv"
CAST_COLUMNS = ["speaker_id", "voice", "basis", "name", "source", "words", "books"]   # then label_<EDITION>..., note


class ConfigError(SystemExit):
    pass


@lru_cache(maxsize=None)
def toml(name: str) -> dict:
    path = CONFIG / name
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        raise ConfigError(f"config/{name} is missing") from None
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"config/{name}: {e}") from None


def merge(a: dict, b: dict) -> dict:
    """``a`` with ``b`` laid over it, table by table."""
    out = dict(a)
    for k, v in (b or {}).items():
        out[k] = merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def edition(name: str | None) -> dict:
    """The edition's block of editions.toml ({} if it has none)."""
    return toml("editions.toml").get(name, {}) if name else {}


@lru_cache(maxsize=None)
def layout(edition_name: str | None = None) -> dict:
    """layout.toml, overridden by the edition's language (languages.toml [<iso>.layout]) and
    then by the edition itself (editions.toml [<EDITION>.layout])."""
    out = toml("layout.toml")
    if edition_name:
        from .fetch import pins
        iso = pins()["editions"].get(edition_name, {}).get("iso")
        out = merge(out, language(iso).get("layout", {}) if iso else {})
        out = merge(out, edition(edition_name).get("layout", {}))
    return out


def cast_rules() -> dict:
    return toml("cast-rules.toml")


def language(iso: str) -> dict:
    return toml("languages.toml").get(iso, {})


@lru_cache(maxsize=None)
def cast_table() -> dict[str, dict]:
    """speaker_id -> row of config/cast.csv (an empty dict if the file is not there yet)."""
    path = CONFIG / CAST_FILE
    if not path.exists():
        return {}
    out: dict[str, dict] = {}
    with path.open(encoding="utf-8-sig", newline="") as f:       # -sig: the BOM Excel writes
        for n, row in enumerate(csv.DictReader(f), start=2):
            sid = (row.get("speaker_id") or "").strip()
            if not sid:
                continue
            voice = (row.get("voice") or "").strip()
            if voice and voice not in VOICES:
                raise ConfigError(f"config/{CAST_FILE} row {n} ({sid}, {row.get('name')}): voice {voice!r} "
                                  f"is not one of {', '.join(VOICES)}")
            row = {k: (v or "").strip() for k, v in row.items() if k}
            row["voice"] = voice
            out[sid] = row
    return out


def write_cast(rows: list[dict], editions: list[str]) -> Path:
    """Write config/cast.csv (UTF-8 with BOM, so Excel shows Hebrew and Greek correctly)."""
    cols = CAST_COLUMNS + [f"label_{e}" for e in editions] + ["note"]
    path = CONFIG / CAST_FILE
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in cols})
    cast_table.cache_clear()
    return path
