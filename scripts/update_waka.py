#!/usr/bin/env python3
"""Update the WakaTime section in README.md using a WakaTime OAuth token."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


README = Path("README.md")
START = "<!--START_SECTION:waka-->"
END = "<!--END_SECTION:waka-->"
BLOCKS = "░▒▓█"


def fetch_stats(token: str) -> dict:
    # WakaTime API keys are write-only. For read access, WakaTime requires OAuth.
    # Its docs explicitly allow passing the personal OAuth token as the api_key
    # query parameter, so the token never needs to appear in request headers or logs.
    query = urlencode({"api_key": token})
    url = f"https://wakatime.com/api/v1/users/current/stats/last_7_days?{query}"
    request = Request(url, headers={"User-Agent": "Nuii-WakaTime-README/1.0"})

    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
                if response.status == 202:
                    if attempt < 2:
                        time.sleep(30)
                        continue
                    raise RuntimeError("WakaTime stats are still being calculated (HTTP 202).")
                return payload.get("data", payload)
        except HTTPError as error:
            detail = ""
            try:
                body = json.loads(error.read().decode("utf-8"))
                detail = body.get("error") or body.get("message") or body.get("errors") or ""
            except (ValueError, UnicodeDecodeError):
                pass

            if error.code == 401:
                raise RuntimeError(
                    "WakaTime rejected the credential (401). Set WAKATIME_OAUTH_TOKEN "
                    "to a valid personal OAuth access token."
                ) from None
            if error.code == 403:
                raise RuntimeError(
                    "WakaTime authenticated the request but denied access (403). "
                    "Check that the OAuth token has read_stats.languages or read_summaries "
                    f"scope. API detail: {detail}"
                ) from None
            raise RuntimeError(f"WakaTime API returned HTTP {error.code}. {detail}") from None
        except URLError as error:
            raise RuntimeError(f"Could not reach WakaTime: {error.reason}") from None

    raise RuntimeError("Unable to fetch WakaTime stats.")


def make_bar(percent: float, width: int = 24) -> str:
    filled = max(0, min(width, round(percent / 100 * width)))
    return BLOCKS[-1] * filled + BLOCKS[0] * (width - filled)


def render_stats(stats: dict) -> str:
    languages = stats.get("languages") or []
    if not languages:
        return "No activity tracked"

    name_width = max(len(str(item.get("name", "Unknown"))) for item in languages)
    lines = []
    for item in languages[:5]:
        name = str(item.get("name", "Unknown"))
        percent = float(item.get("percent", 0))
        duration = str(item.get("text", ""))
        lines.append(
            f"{name.ljust(name_width)}  {duration.ljust(16)} "
            f"{make_bar(percent)}  {percent:5.2f} %"
        )
    return "\n".join(lines)


def main() -> int:
    token = os.environ.get("WAKATIME_OAUTH_TOKEN", "").strip()
    if not token:
        print(
            "Missing WAKATIME_OAUTH_TOKEN. Add a WakaTime personal OAuth access token "
            "as a repository Actions secret.",
            file=sys.stderr,
        )
        return 1

    if not README.is_file():
        print("README.md was not found.", file=sys.stderr)
        return 1

    content = README.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(START) + r"[\s\S]*?" + re.escape(END))
    if not pattern.search(content):
        print("WakaTime section markers were not found in README.md.", file=sys.stderr)
        return 1

    try:
        stats = fetch_stats(token)
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1

    fence = chr(96) * 3
    replacement = f"{START}\n\n{fence}txt\n{render_stats(stats)}\n{fence}\n\n{END}"
    updated = pattern.sub(lambda _: replacement, content, count=1)
    if updated != content:
        README.write_text(updated, encoding="utf-8")
        print("Updated the WakaTime section in README.md.")
    else:
        print("WakaTime stats are unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
