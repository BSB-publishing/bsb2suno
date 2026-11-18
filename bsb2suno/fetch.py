"""Download and cache every input at its pinned revision.

Files land in ``cache/`` (git-ignored) under a path that includes the revision, so changing
a pin in ``pins.json`` never serves a stale file. Nothing here parses data; see the other
modules for that.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache"
USER_AGENT = "bsb2suno/0.1 (+https://github.com/BSB-publishing/bsb2suno)"


class NotFound(Exception):
    """The file does not exist at that revision (HTTP 404)."""


@lru_cache(maxsize=1)
def pins() -> dict:
    return json.loads((ROOT / "pins.json").read_text(encoding="utf-8"))


def _get(url: str, dest: Path, retries: int = 6) -> Path:
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                data = r.read()
            tmp = dest.with_suffix(dest.suffix + ".part")
            tmp.write_bytes(data)
            tmp.replace(dest)
            return dest
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise NotFound(url) from None
            if attempt == retries - 1:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == retries - 1:
                raise
        time.sleep(min(60, 3 * 2 ** attempt))
    raise RuntimeError("unreachable")


def hf(dataset: str, path: str) -> Path:
    """A file of a pinned Hugging Face dataset (key of pins.json "huggingface")."""
    pin = pins()["huggingface"][dataset]
    rev = pin["revision"]
    url = f"https://huggingface.co/datasets/{pin['repo']}/resolve/{rev}/{urllib.parse.quote(path)}"
    return _get(url, CACHE / "hf" / dataset / rev[:12] / path)


def hf_json(dataset: str, path: str):
    return json.loads(hf(dataset, path).read_text(encoding="utf-8"))


def helloao_chapter(translation: str, book: str, chapter: int) -> dict:
    """helloAO's chapter JSON. helloAO has no revisions; the text fingerprint of the
    book (checked against the alignment file name) is what pins the text."""
    url = f"https://bible.helloao.org/api/{translation}/{book}/{chapter}.json"
    p = _get(url, CACHE / "helloao" / translation / book / f"{chapter}.json")
    return json.loads(p.read_text(encoding="utf-8"))


def helloao_books(translation: str) -> dict:
    url = f"https://bible.helloao.org/api/{translation}/books.json"
    p = _get(url, CACHE / "helloao" / translation / "books.json")
    return {b["id"]: b for b in json.loads(p.read_text(encoding="utf-8"))["books"]}
