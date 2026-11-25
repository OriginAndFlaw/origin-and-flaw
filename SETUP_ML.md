# Origin & Flaw ഓട്ടോമേഷൻ: ഒറ്റത്തവണ ചെയ്യേണ്ട സെറ്റപ്പ്

ഇതെല്ലാം **ഒരു തവണ മാത്രം** ചെയ്താൽ മതി. Login, password, OTP, key copy ചെയ്യൽ എന്നിവ നിങ്ങൾ തന്നെ ചെയ്യണം. Key-കൾ ചാറ്റിൽ ഒട്ടിക്കരുത്, നേരിട്ട് GitHub-ൽ മാത്രം ഇടുക.

## എങ്ങനെ പ്രവർത്തിക്കും

```
"Start" (Claude) -> episodes/<ep>/ ഫോൾഡർ (script EN+AR, prompts)
      -> git push -> GitHub Actions "render"
         edge-tts വോയ്സ് (സൗജന്യം) -> auto-editor (pause കുറയ്ക്കും)
         ചിത്രങ്ങൾ: images/ ഫോൾഡർ > Fal.ai FLUX (₹1,000 cap) > Pollinations (സൗജന്യം) > Pexels
         Hook: Google Flow clips (hook/01.mp4 ...), ഇല്ലെങ്കിൽ ചിത്രം
         FFmpeg Ken Burns + vignette + music ducking, Pillow chapter cards + thumbnail
         faster-whisper -> English/Arabic .srt, Shorts-ൽ word captions
      -> long.mp4, short_en.mp4, short_ar.mp4, audio_track_ar.m4a, thumbnail.jpg
      -> (upload mode) YouTube
Research: എല്ലാ ദിവസവും 6:30 AM, outlier വീഡിയോകളും trends-ഉം research/ ഫോൾഡറിൽ
```

## Step 1: GitHub account + repo (സൗജന്യം)
1. github.com-ൽ ഒരു account ഉണ്ടാക്കുക (ഉണ്ടെങ്കിൽ login ചെയ്യുക).
2. **New repository** → പേര് `origin-and-flaw` → **Private** → Create.
3. ഇത്രയും ആയാൽ Claude-നോട് "repo ready" എന്ന് പറയുക. ബാക്കി upload Claude ചെയ്യും.

## Step 2: സൗജന്യ key-കൾ (ഓരോന്നും GitHub → repo → Settings → Secrets and variables → Actions → New repository secret)

| Secret പേര് | എവിടെ നിന്ന് | വേണോ? |
|---|---|---|
| `YOUTUBE_API_KEY` | console.cloud.google.com → APIs → "YouTube Data API v3" Enable → Credentials → API key | Research-ന് വേണം (സൗജന്യം) |
| `PEXELS_API_KEY` | pexels.com/api | ഐച്ഛികം (സൗജന്യം) |
| `FAL_KEY` | fal.ai → Keys | ഐച്ഛികം. **പണം**: ₹1,000 cap code-ൽ ഉണ്ട്. Card ചേർക്കുന്നത് നിങ്ങൾ |

`FAL_KEY` ഇല്ലെങ്കിലും video വരും: ചിത്രങ്ങൾ Pollinations-ൽ (സൗജന്യം) നിന്ന് എടുക്കും.

## Step 3: YouTube upload (ഐച്ഛികം)
- ആദ്യത്തെ ആഴ്ചകളിൽ **upload കൈകൊണ്ട്** ചെയ്യുന്നതാണ് നല്ലത്: Actions run-ലെ **Artifacts** ഡൗൺലോഡ് ചെയ്ത് Studio-യിൽ ഇടുക. Arabic audio track (`audio_track_ar.m4a`) Studio → Languages → Add audio-ൽ ചേർക്കാം.
- പൂർണ്ണ auto വേണമെങ്കിൽ: Google Cloud-ൽ OAuth client (Desktop) ഉണ്ടാക്കി `python tools/get_refresh_token.py client_secret.json` (ചാനലിന്റെ account-ൽ നിങ്ങൾ login ചെയ്യണം) → കിട്ടുന്ന 3 വാല്യൂ secrets ആയി ഇടുക (`YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`) → Variables-ൽ `UPLOAD_MODE` = `api`.
  - ശ്രദ്ധിക്കുക: Google audit കഴിയാത്ത project-ൽ നിന്ന് upload ചെയ്യുന്നത് **private** ആയി മാത്രമേ വരൂ. Audit സൗജന്യമാണ്, അപേക്ഷിക്കാം.

## Step 4: Make.com trigger (ഐച്ഛികം)
Sheet-ൽ നിന്ന് തുടങ്ങണമെങ്കിൽ: Make scenario → Google Sheets "Watch rows" → HTTP "Make a request":
`POST https://api.github.com/repos/<user>/origin-and-flaw/dispatches`, header `Authorization: Bearer <GitHub fine-grained token, Contents: read/write>`,
body `{"event_type":"render-episode","client_payload":{"episode":"{{episode column}}"}}`.
Make ഇല്ലാതെയും പറ്റും: GitHub → Actions → render → **Run workflow** → episode പേര്.

## Step 5: Music (സൗജന്യം)
YouTube Studio → **Audio Library**-ൽ നിന്ന് 5-10 dark/cinematic track ഡൗൺലോഡ് ചെയ്ത് `assets/music/`-ൽ ഇടുക (attribution വേണ്ടാത്തവ മാത്രം).

## ചെലവ്
- GitHub Actions: private repo-ക്ക് മാസം 2,000 മിനിറ്റ് സൗജന്യം. ഒരു എപ്പിസോഡിന് ~35-50 മിനിറ്റ് → 12 എപ്പിസോഡ് സുരക്ഷിതം.
- edge-tts, faster-whisper, auto-editor, FFmpeg, Pillow, Pollinations, pytrends: ₹0.
- Fal.ai: ഒരു ചിത്രം ~$0.003 (FLUX schnell). ഒരു എപ്പിസോഡ് (25 ചിത്രം) ≈ ₹7. Cap ₹1,000.
- Chirp 3 HD: Google Cloud billing (card) വേണം; അതുകൊണ്ട് default edge-tts ആണ്.
