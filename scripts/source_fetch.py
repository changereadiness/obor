#!/usr/bin/env python3
"""Source transport for OBOR clean integration.

Transport is deliberately separated from semantic extraction. Tests may supply
an explicit URL->fixture map through OBOR_SOURCE_FIXTURE_MAP; production uses
normal HTTP fetching. No semantic fallback exists here.
"""
from __future__ import annotations
import json, os, time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

UA = "OBOR/clean-m6 (+https://obor.ca)"
TIMEOUT = 15
RETRIES = 2
MAX_BYTES = 5 * 1024 * 1024


def _fixture_map() -> dict[str, str]:
    path = os.environ.get("OBOR_SOURCE_FIXTURE_MAP")
    if not path:
        return {}
    return json.loads(Path(path).read_text())


def fetch_source(url: str):
    if not url:
        raise ValueError("empty source URL")
    fixtures = _fixture_map()
    if url in fixtures:
        body = Path(fixtures[url]).read_bytes()
        return body, "text/html; charset=utf-8", 200

    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.1",
        "Accept-Language": "en-CA,en;q=0.8",
        "Cache-Control": "no-cache",
    }
    last = None
    for attempt in range(RETRIES + 1):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=TIMEOUT) as response:
                return response.read(MAX_BYTES + 1)[:MAX_BYTES], response.headers.get("Content-Type", ""), response.status
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last = exc
            if attempt < RETRIES:
                time.sleep(1.5 * (attempt + 1))
    raise last
