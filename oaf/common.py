"""Shared helpers: config, paths, logging, running ffmpeg."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
EPISODES = ROOT / "episodes"
OUT = ROOT / "out"


def load_config() -> dict:
    with open(ROOT / "config.yml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def log(msg: str) -> None:
    print(f"[oaf] {msg}", flush=True)


def run(cmd: list[str], quiet: bool = True) -> str:
    """Run a command; raise with its stderr tail when it fails."""
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        tail = "\n".join((p.stderr or p.stdout).splitlines()[-25:])
        raise RuntimeError(f"command failed: {' '.join(cmd[:6])} ...\n{tail}")
    if not quiet:
        print(p.stdout)
    return p.stdout


def need(binary: str) -> str:
    path = shutil.which(binary)
    if not path:
        sys.exit(f"{binary} is not installed or not on PATH")
    return path


def duration(path: Path | str) -> float:
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)])
    return float(json.loads(out)["format"]["duration"])


def env(name: str) -> str | None:
    v = os.environ.get(name, "").strip()
    return v or None


def load_episode(ep_id: str) -> tuple[dict, Path]:
    folder = EPISODES / ep_id
    if not folder.is_dir():
        sys.exit(f"episode folder not found: {folder}")
    with open(folder / "episode.json", encoding="utf-8") as f:
        return json.load(f), folder


def ff_path(p: Path | str) -> str:
    """Path usable inside an ffmpeg filter argument (Windows drive colon escaped)."""
    s = str(Path(p).resolve()).replace("\\", "/")
    if len(s) > 1 and s[1] == ":":
        s = s[0] + "\\:" + s[2:]
    return s.replace("'", "\\'")
