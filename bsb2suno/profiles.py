"""Song profile of a book in an edition (config/profiles.toml, books.toml, editions.toml)."""
from __future__ import annotations

import copy
from dataclasses import dataclass

from .config import VOICES, ConfigError, toml


@dataclass
class Profile:
    name: str
    lead: str                   # 'female' or 'male'
    style: str
    persona: str | None         # the Suno persona to select, if set
    tags: dict[str, str]        # voice class -> lyric tag


def _merge(a: dict, b: dict) -> dict:
    out = copy.deepcopy(a)
    for k, v in (b or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else copy.deepcopy(v)
    return out


def for_book(edition: str, book: str, profile: str | None = None, lead: str | None = None) -> Profile:
    books = toml("books.toml")
    profs = toml("profiles.toml")
    ed = toml("editions.toml").get(edition, {})

    pick: dict = {}
    for layer in (books.get("default"), books.get("books", {}).get(book),
                  ed.get("default"), ed.get("books", {}).get(book)):
        pick = _merge(pick, layer or {})
    name = profile or pick.get("profile")
    lead = lead or pick.get("lead") or "male"
    if name not in profs.get("profiles", {}):
        raise ConfigError(f"config/books.toml or editions.toml: book {book} has profile {name!r}, which is not in "
                          f"config/profiles.toml; choose from {', '.join(profs.get('profiles', {}))}")
    if lead not in ("female", "male"):
        raise ConfigError(f"config/books.toml: book {book} has lead {lead!r}; use \"female\" or \"male\"")

    p = _merge(profs["profiles"][name], ed.get("profiles", {}).get(name, {}))
    if not p.get("style"):
        raise ConfigError(f"config/profiles.toml: profile {name!r} has no style")
    tags = _merge(profs.get("tags", {}), p.get("tags", {}))
    unknown = sorted(set(tags) - set(VOICES) - {"refrain"})
    if unknown:
        raise ConfigError(f"config/profiles.toml: unknown voice tag name(s) {', '.join(unknown)} "
                          f"(profile {name}); allowed: {', '.join(VOICES)}, refrain")
    return Profile(name=name, lead=lead, style=p["style"] + (ed.get("style_suffix") or ""),
                   persona=(p.get("persona") or {}).get(lead) or None, tags=tags)
