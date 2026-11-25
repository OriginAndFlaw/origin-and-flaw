"""Stills for every FLUX scene: a ready-made file first, then Fal.ai (budget-capped), Pollinations, Pexels."""
from __future__ import annotations

import datetime as dt
import json
import time
import urllib.parse
from pathlib import Path

import requests
from PIL import Image, ImageDraw

from .common import ROOT, env, log

LEDGER = ROOT / "budget" / "fal_ledger.json"


def _ledger() -> dict:
    if LEDGER.exists():
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    return {}


def _month() -> str:
    return dt.date.today().strftime("%Y-%m")


def fal_spent() -> float:
    return _ledger().get(_month(), 0.0)


def _fal_charge(usd: float) -> None:
    led = _ledger()
    led[_month()] = round(led.get(_month(), 0.0) + usd, 4)
    LEDGER.parent.mkdir(exist_ok=True)
    LEDGER.write_text(json.dumps(led, indent=2), encoding="utf-8")


def _save(url: str, dst: Path) -> bool:
    r = requests.get(url, timeout=120)
    if r.status_code != 200 or len(r.content) < 5000:
        return False
    dst.write_bytes(r.content)
    Image.open(dst).convert("RGB").save(dst.with_suffix(".jpg"), quality=93)
    if dst.suffix != ".jpg":
        dst.unlink()
    return True


def from_fal(prompt: str, dst: Path, cfg: dict) -> bool:
    key = env("FAL_KEY")
    ic = cfg["images"]
    if not key:
        return False
    if fal_spent() + ic["fal_usd_per_image"] > ic["fal_monthly_cap_usd"]:
        log(f"Fal.ai monthly cap reached (${fal_spent():.2f}): skipping Fal")
        return False
    r = requests.post(f"https://fal.run/{ic['fal_model']}", timeout=180,
                      headers={"Authorization": f"Key {key}"},
                      json={"prompt": prompt, "image_size": "landscape_16_9", "num_images": 1,
                            "enable_safety_checker": True})
    if r.status_code != 200:
        log(f"Fal.ai error {r.status_code}: {r.text[:200]}")
        return False
    _fal_charge(ic["fal_usd_per_image"])
    return _save(r.json()["images"][0]["url"], dst)


def from_pollinations(prompt: str, dst: Path, cfg: dict) -> bool:
    url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt[:900]) +
           "?width=1920&height=1080&nologo=true&model=flux&seed=" + str(abs(hash(prompt)) % 100000))
    for attempt in range(3):
        try:
            if _save(url, dst):
                return True
        except requests.RequestException as e:
            log(f"pollinations attempt {attempt + 1}: {e}")
        time.sleep(6)
    return False


def from_pexels(query: str, dst: Path, cfg: dict) -> bool:
    key = env("PEXELS_API_KEY")
    if not key:
        return False
    r = requests.get("https://api.pexels.com/v1/search", headers={"Authorization": key}, timeout=60,
                     params={"query": query[:80], "orientation": "landscape", "per_page": 1, "size": "large"})
    photos = r.json().get("photos", []) if r.status_code == 200 else []
    return bool(photos) and _save(photos[0]["src"]["original"], dst)


def placeholder(text: str, dst: Path) -> None:
    im = Image.new("RGB", (1920, 1080), (10, 30, 34))
    ImageDraw.Draw(im).text((80, 500), text[:120], fill=(232, 168, 72))
    im.save(dst, quality=90)


def get_still(scene: dict, folder: Path, cfg: dict) -> Path:
    """Return a .jpg for this scene, making it if needed. Files in <episode>/images/NN.jpg always win."""
    img_dir = folder / "images"
    img_dir.mkdir(exist_ok=True)
    n = int(scene["n"])
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        p = img_dir / f"{n:02d}{ext}"
        if p.exists():
            return p
    dst = img_dir / f"{n:02d}.jpg"
    prompt = scene["prompt"]
    if cfg["images"]["style"].split(",")[0] not in prompt:
        prompt = f"{prompt}, {cfg['images']['style']}"
    makers = {"fal": from_fal, "pollinations": from_pollinations,
              "pexels": lambda p, d, c: from_pexels(scene.get("stock_query") or scene["prompt"], d, c)}
    for name in cfg["images"]["order"]:
        if name == "local" or name not in makers:
            continue
        try:
            if makers[name](prompt, dst, cfg):
                log(f"scene {n:02d}: still from {name}")
                return dst
        except Exception as e:  # one bad source must not stop the render
            log(f"scene {n:02d}: {name} failed: {e}")
    log(f"scene {n:02d}: NO SOURCE WORKED, placeholder used")
    placeholder(scene["prompt"], dst)
    return dst
