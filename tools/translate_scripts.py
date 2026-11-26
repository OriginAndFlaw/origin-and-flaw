"""Translate an episode's English narration into the dub languages (free Google endpoint, run on a PC).

    python -X utf8 tools/translate_scripts.py ep04-teflon            # every language in config dubs
    python -X utf8 tools/translate_scripts.py ep04-teflon es pt     # only these

Writes episodes/<ep>/script_<lang>.txt and short_<lang>.txt next to the English ones. A script that
already exists is never overwritten (Arabic is written by hand), so hand-fixed files stay.
Read a few lines of every result before rendering: names, numbers and units must survive.
"""
import json
import sys
import time
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
URL = "https://translate.googleapis.com/translate_a/single"


def tr(text: str, lang: str) -> str:
    for attempt in range(5):
        r = requests.get(URL, params={"client": "gtx", "sl": "en", "tl": lang, "dt": "t", "q": text}, timeout=30)
        if r.status_code == 200:
            return "".join(part[0] for part in r.json()[0] if part[0])
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"translation to {lang} failed: HTTP {r.status_code}")


def translate_file(src: Path, dst: Path, lang: str) -> None:
    if dst.exists():
        print(f"keep {dst.name}")
        return
    paras = src.read_text(encoding="utf-8").split("\n\n")
    out = []
    for p in paras:
        out.append(tr(p.strip(), lang) if p.strip() else "")
        time.sleep(0.6)
    dst.write_text("\n\n".join(out).strip() + "\n", encoding="utf-8")
    print(f"wrote {dst.name}: {len(dst.read_text(encoding='utf-8').split())} words")


def main() -> None:
    ep_id = sys.argv[1]
    cfg = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))
    langs = sys.argv[2:] or [l for l in cfg["dubs"] if l != "ar"]
    folder = ROOT / "episodes" / ep_id
    ep = json.loads((folder / "episode.json").read_text(encoding="utf-8"))
    for lang in langs:
        translate_file(folder / ep["scripts"]["en"], folder / f"script_{lang}.txt", lang)
        if ep.get("short", {}).get("en"):
            translate_file(folder / ep["short"]["en"], folder / f"short_{lang}.txt", lang)


if __name__ == "__main__":
    main()
