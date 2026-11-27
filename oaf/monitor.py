"""Daily channel check (runs in GitHub Actions after the evening post, needs no PC).

Looks at what queue/published.txt says went out today and at the channel's public feed, then checks each new video:
public and playable, the right length (long video 8+ min, Short 60 s or less), a thumbnail. Any problem -> exit 1 with
a plain report, and the workflow opens a GitHub issue (GitHub emails the owner)."""
import datetime as dt
import json
import re
import sys
import urllib.request

CHANNEL = "UCMiYbEnO-XaUWqHFk7KmF2A"
UA = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en"}


def get(url: str) -> str:
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read().decode("utf-8", "replace")


def details(vid: str) -> dict:
    h = get(f"https://www.youtube.com/watch?v={vid}")
    m = re.search(r"ytInitialPlayerResponse\s*=\s*(\{.+?\});(?:var|</script>)", h, re.S)
    p = json.loads(m.group(1)) if m else {}
    d = p.get("videoDetails", {})
    mf = p.get("microformat", {}).get("playerMicroformatRenderer", {})
    return {"title": d.get("title", "?"), "seconds": int(d.get("lengthSeconds") or 0),
            "status": p.get("playabilityStatus", {}).get("status"), "unlisted": mf.get("isUnlisted"),
            "thumbs": len(d.get("thumbnail", {}).get("thumbnails", []))}


def main() -> int:
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    lines = [l.split() for l in open("queue/published.txt", encoding="utf-8").read().splitlines() if l.strip()]
    todays = [l for l in lines if len(l) > 1 and l[1] == today]
    feed = get(f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL}")
    entries = re.findall(r"<entry>.*?<yt:videoId>([^<]*)</yt:videoId>.*?<title>([^<]*)</title>.*?<published>([^<]*)</published>", feed, re.S)
    new = [(v, t) for v, t, p in entries if p.startswith(today)]
    problems, report = [], []
    if not todays:
        problems.append(f"Nothing was published by the workflow today ({today}). Check queue/publish.txt and the publish run.")
    expected = 0
    for l in todays:
        expected += 1 if len(l) > 2 else 2  # an extra Short alone, or long video + its Short
    if todays and len(new) < expected:
        problems.append(f"Expected {expected} new video(s) on the channel today, found {len(new)}: {[t for _, t in new]}")
    for vid, title in new:
        d = details(vid)
        short = "#shorts" in title.lower() or d["seconds"] <= 60
        line = f"{title} | {d['seconds'] // 60}:{d['seconds'] % 60:02d} | {d['status']} | thumbs {d['thumbs']} | https://youtu.be/{vid}"
        report.append(line)
        if d["status"] != "OK" or d["unlisted"]:
            problems.append(f"Not public/playable: {line}")
        if not short and d["seconds"] < 480:
            problems.append(f"Long video under 8 minutes: {line}")
        if short and d["seconds"] > 60:
            problems.append(f"Short longer than 60 s: {line}")
        if d["thumbs"] == 0:
            problems.append(f"No thumbnail: {line}")
    print("Today's videos:\n" + ("\n".join(report) or "(none)"))
    if problems:
        print("\nPROBLEMS:\n" + "\n".join(problems))
        open("monitor_problems.txt", "w", encoding="utf-8").write("\n".join(problems + ["", "Today's videos:"] + report))
        return 1
    print("\nAll good.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
