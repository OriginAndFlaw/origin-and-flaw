"""Turn a 5-part episode package (Markdown, as Claude writes it) into episodes/<id>/ ready to render.

python tools/from_package.py path/to/EP01_package.md ep01-hyatt-regency
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def section(md: str, n: int) -> str:
    m = re.search(rf"^## {n}\..*?$(.*?)(?=^## {n + 1}\.|\Z)", md, re.S | re.M)
    return m.group(1).strip() if m else ""


def body_text(s: str) -> str:
    s = re.sub(r"^---\s*$", "", s, flags=re.M)
    return s.strip() + "\n"


def secs(t: str) -> float:
    m, s = t.split(":")
    return int(m) * 60 + float(s)


def main(pkg: str, ep_id: str) -> None:
    md = Path(pkg).read_text(encoding="utf-8")
    folder = ROOT / "episodes" / ep_id
    (folder / "hook").mkdir(parents=True, exist_ok=True)
    (folder / "images").mkdir(exist_ok=True)

    pack = section(md, 1)
    titles = re.findall(r"^\d\. (.+?)(?: \(\d+\))?$", pack.split("**Thumbnail")[0], re.M)
    thumb_words = re.search(r"Text: \*\*(.+?)\*\*", pack)
    desc = re.search(r"\*\*Description.*?\*\*\n(.*?)\n\*\*Tags\*\*", pack, re.S)
    tags = re.search(r"\*\*Tags\*\*\n(.+)", pack)
    thumb_scene = re.search(r"\*\*Thumbnail still:\*\* scene (\d+)", pack)
    chapters = re.findall(r"^(\d+:\d\d) (.+)$", desc.group(1) if desc else "", re.M)

    scenes = []
    for row in re.findall(r"^\| (\d+) \| ([^|]+) \| ([^|]+) \| ([^|]+) \| ([^|]+) \|$", section(md, 2), re.M):
        n, t, tool, prompt, sfx = (x.strip() for x in row)
        t = t.split("-")[0]
        sc = {"n": int(n), "t": t, "tool": "flow" if "FLOW" in tool.upper() else "flux",
              "prompt": prompt, "sfx": sfx}
        if sc["tool"] == "flow":
            sc["clip"] = f"hook/{int(n):02d}.mp4"
        scenes.append(sc)
    # a chapter title shows on the first still at or after its time (the first chapter is the hook: skipped)
    for ct, title in chapters[1:]:
        later = [s for s in scenes if s["tool"] == "flux" and secs(s["t"]) >= secs(ct) - 1]
        if later:
            later[0]["chapter"] = title.strip()

    (folder / "script_en.txt").write_text(body_text(section(md, 3)), encoding="utf-8")
    (folder / "script_ar.txt").write_text(body_text(section(md, 4)), encoding="utf-8")
    short = section(md, 5)
    en = re.search(r"\*\*English.*?\*\*\n(.*?)\n\*\*Arabic", short, re.S)
    ar = re.search(r"\*\*Arabic.*?\*\*\n(.*?)\n\*\*Short title", short, re.S)
    hook = re.search(r"\*\*Visual hook.*?:\*\* (.+)", short)
    stitle = re.search(r"\*\*Short title:\*\* (.+)", short)
    (folder / "short_en.txt").write_text(en.group(1).strip() + "\n" if en else "", encoding="utf-8")
    (folder / "short_ar.txt").write_text(ar.group(1).strip() + "\n" if ar else "", encoding="utf-8")

    body = [s for s in scenes if s["tool"] == "flux"]
    pick = [body[int(i * (len(body) - 1) / 4)]["n"] for i in range(5)] if len(body) >= 5 else [s["n"] for s in body]
    ep = {
        "id": ep_id,
        "title": titles[0] if titles else ep_id,
        "alt_titles": titles[1:],
        "description": desc.group(1).strip() if desc else "",
        "tags": [x.strip() for x in tags.group(1).split(",")] if tags else [],
        "thumbnail": {"scene": int(thumb_scene.group(1)) if thumb_scene else pick[len(pick) // 2],
                      "words": thumb_words.group(1).strip() if thumb_words else ""},
        "hook_seconds": 20,
        "scripts": {"en": "script_en.txt", "ar": "script_ar.txt"},
        "scenes": scenes,
        "short": {
            "title": stitle.group(1).strip() if stitle else "",
            "en": "short_en.txt", "ar": "short_ar.txt",
            "scenes": ([{"n": "s1", "tool": "flow", "prompt": hook.group(1).strip(), "clip": "hook/short.mp4",
                         "use": pick[0]}] if hook else []) + [{"tool": "flux", "use": n} for n in pick],
        },
    }
    (folder / "episode.json").write_text(json.dumps(ep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{folder}: {len(scenes)} scenes, {len(chapters)} chapters, title: {ep['title']}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
