# Seat 17 - Algorithm report, 26 Nov 2026

Sources are YouTube's own pages unless marked. [3P] = third-party data. RUMOUR = do not build on it.

## What the system rewards
- **The viewer, not the video.** Recommendations try to match each viewer with videos "they're likely to watch and
  enjoy". Signals: watch and search history, likes/dislikes, "Don't recommend channel", and **satisfaction surveys**
  (1-5 star "valued watch time"), not raw watch time alone. Home relies on watch history, Up Next on the current
  video. Time of day and device also count. (Help 16089387; blog.youtube "On YouTube's recommendation system")
- **Click AND stay.** YouTube's own A/B test picks the winning title/thumbnail by **watch time, not CTR**
  (Help 16391400). A click that leaves early is a loss.
- **Long videos:** no ideal length. What counts is "sustaining engagement throughout the entire video": read the
  retention curve (Help 16559651).
- **Shorts:** ranked separately. Shorts "may favor recent content", and preferences differ by format even within
  one topic (Help 16559651). Public Shorts views count from the first play; monetisation uses **engaged views**
  (blog.youtube "Engaged views, explained", Mar 2025). Long-form public views also count from the first frame since
  24 Aug 2026; watch hours for YPP are still engaged (SEJ, Engadget).
- **Multi-language audio:** creators with extra audio tracks got **over 25% of watch time** from non-primary
  languages (Help 13338784; blog.youtube). Supports our Spanish track.

## What it punishes or ignores
- **Inauthentic content (monetisation, whole channel).** Updated guidance July 2026, same rules: (1) generic or
  repetitive content - template look, image slideshows, AI built on generic templates with no creator insight;
  (2) unsatisfying content - stitched AI clips with no narrative arc, fake realistic visuals of disasters;
  (3) AI personas posing as experts on health/legal/financial/political topics (Help 1311392; Tubefilter
  13 Jul 2026). Our biggest risk: every episode must vary in structure and carry real research and opinion.
- **Viewers who keep abandoning us:** repeated stop-watching of recommended videos hurts over time. One weak video
  does NOT penalise the channel (Help 16559651).
- **Clickbait mismatch** shows up as short watch time and low survey scores, which is exactly what the system
  measures (Help 16089387).
- **Ignored:** subscriber count (watch "Unique viewers" instead), monetisation status, uploading unlisted first,
  waiting 24-48 h before publishing (Rene Ritchie, via SEJ). Fake engagement / sub-for-sub breaks the Fake Engagement
  policy and is never used.
- **Posting gaps:** no official penalty found. [3P] vidIQ (10M channels): more uploads, more growth; OverseerOS:
  shorter gaps do not make the next video more likely to break out. "The algorithm punishes gaps" = RUMOUR.

## How a new channel gets its first push
- No history means no subscriber pull: Browse and Suggested try a video on small groups and widen if they stay and
  are satisfied (YouTube's recommendation description; [3P] TubeBuddy). Search works from day one for clear topics.
- "A substantial library of quality videos" helps new viewers explore and teaches the system (Help 16559651).
- Shorts to long: viewers often don't cross formats. Since 2025 YouTube can recommend a channel's recent long videos
  to people who watch its Shorts ([3P] vidIQ, citing YouTube). The tool that does it on purpose is the Shorts
  **related video** link (Help 14075157); make the Short's promise match the long video's opening
  (blog.youtube related-videos guide). Expect few conversions; Shorts mainly buy reach and subscribers.

## Rules for Origin & Flaw
1. **Titles/thumbnails are a promise the first 30 s keeps.** Run Test & Compare (3 variants, clearly different) on
   every episode; the winner is judged by watch time. (Help 16391400)
2. **First 30 s:** start in the strangest moment, show the thing the thumbnail shows within 15 s, no channel intro.
   (Help 16559651 retention; playbook)
3. **Length follows retention, not a number.** Keep 9-11 min while the curve holds; cut sections where it dips.
   (Help 16559651)
4. **Never templated.** Different opening and structure each episode, own commentary, diagrams, a clear story arc;
   no plain slideshow. (Help 1311392, July 2026 guidance)
5. **Upload time:** publish when our viewers are on (Studio > Audience > "When your viewers are on YouTube"). Until
   we have data, aim at US/UK evening: 14:00-16:00 US Eastern = 19:00-21:00 UK = 22:00-24:00 Qatar. Avoid off hours
   (Ritchie: slower first boost). The slot itself is [3P] advice.
6. **Publish when ready;** no holding back unlisted for 24-48 h. (Ritchie, SEJ)
7. **Rhythm:** a steady weekly long video plus one Short a day. Quality first; a gap is not a penalty. ([3P] vidIQ)
8. **Every Short gets a related-video link** to the matching episode, with a spoken pointer. (Help 14075157)
9. **End screen + playlists** to the next episode in the same series; the teaser line must point to a real video.
   (YouTube end-screen/playlist tools; Up Next uses the current video - Help 16089387)
10. **Spanish audio track** on every episode. (Help 13338784, 25%+)
11. **Watch Unique viewers, retention and engaged views,** not subscribers or public views. (Help 16559651)
12. **Label AI content** where YouTube asks (altered/synthetic disclosure); no AI "expert" persona.
    (Help 1311392)

## Sources
- https://support.google.com/youtube/answer/16089387 (How recommendations work)
- https://support.google.com/youtube/answer/16559651 (Good to know about recommendations)
- https://blog.youtube/inside-youtube/on-youtubes-recommendation-system/
- https://support.google.com/youtube/answer/16391400 (A/B test titles & thumbnails)
- https://support.google.com/youtube/answer/1311392 (Monetisation policies, inauthentic content)
- https://www.tubefilter.com/2026-07-13/youtube-inauthentic-content-monetization-policy-update/
- https://blog.youtube/inside-youtube/engaged-views-youtube-explained/
- https://www.searchenginejournal.com/youtube-changes-how-it-counts-views-on-long-form-live/586166/
- https://www.searchenginejournal.com/youtube-debunks-24-48-hour-upload-delay-recommendation/560613/
- https://searchengineland.com/youtube-issues-guidance-on-when-to-post-content-for-maximum-reach-438774
- https://support.google.com/youtube/answer/14075157 (Related video on Shorts)
- https://blog.youtube/creator-and-artist-stories/youtube-related-videos-traffic-guide/
- https://support.google.com/youtube/answer/13338784 (Multi-language audio)
- https://vidiq.com/research/youtube-upload-frequency-study/ [3P]
- https://vidiq.com/blog/post/youtube-recommends-long-form-videos-shorts-viewers [3P]
