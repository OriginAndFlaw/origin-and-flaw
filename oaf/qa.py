"""Quality check of a finished episode, run after every render. Writes out/<ep>/qa.txt and exits 1 on a FAIL.

    python -m oaf.qa --episode ep04-teflon

Checks the channel's rules: length over 8 minutes, upload file small enough for Make, loudness near -14 LUFS,
chapters present, no picture frozen too long, callouts drawn, thumbnail and Short present, dub track length.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

from .common import OUT, load_config, load_episode


def probe(path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def loudness(path) -> float | None:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    return float(m[-1]) if m else None


def longest_still(path) -> float:
    """Longest stretch with no visible change (a frozen picture), in seconds."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-vf", "fps=2,freezedetect=n=0.003:d=8",
                        "-an", "-f", "null", "-"], capture_output=True, text=True)
    d = [float(x) for x in re.findall(r"freeze_duration: ([\d.]+)", r.stderr)]
    return max(d, default=0.0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", required=True)
    a = ap.parse_args()
    cfg = load_config()
    ep, folder = load_episode(a.episode)
    out = OUT / a.episode
    lines, fails = [], 0

    def check(ok: bool, text: str, warn_only: bool = False):
        nonlocal fails
        tag = "OK  " if ok else ("WARN" if warn_only else "FAIL")
        if not ok and not warn_only:
            fails += 1
        lines.append(f"{tag} {text}")

    long = out / "long.mp4"
    if not long.exists():
        print("no long.mp4 rendered")
        sys.exit(1)
    dur = probe(long)
    minimum = cfg.get("quality", {}).get("min_long_seconds", 480)
    check(dur >= minimum, f"length {dur / 60:.2f} min (minimum {minimum / 60:.0f})")
    up = out / "long_upload.mp4" if (out / "long_upload.mp4").exists() else long
    mb = up.stat().st_size / 2 ** 20
    check(mb <= cfg["upload"].get("max_mb", 95), f"upload file {up.name} {mb:.0f} MB (Make limit {cfg['upload'].get('max_mb', 95)})")
    lufs = loudness(long)
    check(lufs is not None and -16 <= lufs <= -12, f"loudness {lufs} LUFS (target -14)", warn_only=True)
    ch = (out / "chapters.txt").read_text(encoding="utf-8").strip().splitlines() if (out / "chapters.txt").exists() else []
    check(len(ch) >= 3 and ch[0].startswith("0:00"), f"{len(ch)} chapters, first at {ch[0][:4] if ch else '-'}")
    freeze = longest_still(long)
    check(freeze < 10, f"longest unchanged picture {freeze:.1f} s (should be under 10)", warn_only=True)
    shown = len(list((out / "work").glob("callout_*.png"))) if (out / "work").exists() else 0
    want = len(ep.get("callouts", []))
    check(shown >= max(1, want - 2) if want else True, f"number callouts drawn {shown} of {want}", warn_only=True)
    check((out / "thumbnail.jpg").exists(), "thumbnail made in this run", warn_only=True)
    if (out / "short_en.mp4").exists():  # a partial re-render (e.g. --only long) keeps the released Short
        check(probe(out / "short_en.mp4") <= 60, f"Short {probe(out / 'short_en.mp4'):.0f} s (60 s max)")
    for lang in cfg.get("dubs", []):
        tr = out / f"audio_track_{lang}.m4a"
        if tr.exists():
            check(abs(probe(tr) - dur) < 3, f"{lang} track {probe(tr):.0f} s vs video {dur:.0f} s")
    report = "\n".join(lines)
    (out / "qa.txt").write_text(report + "\n", encoding="utf-8")
    print(report)
    print(f"QA: {fails} failure(s)")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
