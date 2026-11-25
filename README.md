# Origin & Flaw pipeline

Zero-cost documentary pipeline for the YouTube channel @OriginAndFlaw (English + Arabic).

| Step | Tool (open source / free) |
|---|---|
| Voice | edge-tts (default) or Google Cloud TTS Chirp 3 HD |
| Dead-air trim | auto-editor (ffmpeg silenceremove fallback) |
| Stills | episode `images/` > Fal.ai FLUX schnell (monthly cap in `config.yml`) > Pollinations > Pexels |
| Hook | Google Flow clips in `episodes/<ep>/hook/NN.mp4` |
| Edit | FFmpeg: Ken Burns (zoompan), vignette, sidechain music ducking, loudnorm -14 LUFS |
| Graphics | Pillow: chapter cards, thumbnail |
| Subtitles | faster-whisper word timestamps -> .srt (long) and word-highlight .ass (Shorts) |
| Upload | YouTube Data API v3 or a Make.com webhook (`upload.mode`) |
| Research | YouTube Data API v3 outliers, pytrends, youtube-transcript-api hooks |

```
python tools/from_package.py EP01_package.md ep01-hyatt-regency   # package -> episodes/<ep>/
python -m oaf.render --episode ep01-hyatt-regency [--test] [--only long,arabic,short,thumb]
python -m oaf.upload --episode ep01-hyatt-regency
python -m oaf.research
```

Outputs in `out/<ep>/`: `long.mp4`, `long_en.srt`, `long_ar.srt`, `audio_track_ar.m4a` (for YouTube's
multi-language audio, added in Studio), `short_en.mp4`, `short_ar.mp4`, `thumbnail.jpg`.

GitHub Actions: `render.yml` (repository_dispatch `render-episode` or manual) and `research.yml` (daily).
Setup steps (Malayalam): `SETUP_ML.md`.
