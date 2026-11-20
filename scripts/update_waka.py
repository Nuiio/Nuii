#!/usr/bin/env python3
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API_URL = "https://api.wakatime.com/api/v1/users/current/stats/last_7_days"
README_PATH = "README.md"
START = "<!--START_SECTION:waka-->"
END = "<!--END_SECTION:waka-->"


def fetch_stats(token):
    query = urllib.parse.urlencode({"api_key": token})
    request = urllib.request.Request(
        f"{API_URL}?{query}",
        headers={"Accept": "application/json", "User-Agent": "Nuii-WakaTime-Updater/1.0"},
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if "data" not in payload:
                raise RuntimeError("Unexpected WakaTime response: " + str(payload))
            return payload["data"]
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            if error.code == 429 and attempt < 2:
                time.sleep(10 * (attempt + 1))
                continue
            raise RuntimeError("WakaTime API returned HTTP " + str(error.code) + ": " + detail)
        except urllib.error.URLError as error:
            if attempt < 2:
                time.sleep(3 * (attempt + 1))
                continue
            raise RuntimeError("Unable to reach WakaTime API: " + str(error))
    raise RuntimeError("WakaTime API request failed")


def render(data):
    languages = data.get("languages") or []
    if not languages:
        return "No coding activity recorded in the last 7 days."

    lines = []
    for language in languages[:10]:
        name = str(language.get("name", "Unknown"))[:22]
        duration = str(language.get("text", "0 secs"))
        percent = float(language.get("percent", 0))
        filled = max(0, min(20, round(percent / 5)))
        bar = "█" * filled + "░" * (20 - filled)
        lines.append(f"{name:<22} {duration:<18} {bar} {percent:5.2f} %")
    fence = chr(96) * 3
    return "Last 7 Days\n\n" + fence + "txt\n" + "\n".join(lines) + "\n" + fence


def main():
    token = os.environ.get("WAKATIME_OAUTH_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Missing GitHub Actions secret: WAKATIME_OAUTH_TOKEN")

    with open(README_PATH, "r", encoding="utf-8") as file:
        readme = file.read()

    if START not in readme or END not in readme:
        raise RuntimeError("README.md is missing the WakaTime section markers")

    data = fetch_stats(token)
    section = render(data)
    before, remainder = readme.split(START, 1)
    _, after = remainder.split(END, 1)
    updated = before + START + "\n\n" + section + "\n\n" + END + after

    with open(README_PATH, "w", encoding="utf-8", newline="\n") as file:
        file.write(updated)

    print("WakaTime stats updated successfully.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("::error::" + str(error), file=sys.stderr)
        sys.exit(1)
