# Design assets

## Hero clip

| File | Size | Role |
|---|---|---|
| `hero-loop.webm` | ~2.3 MB | **What actually plays.** 600x600 VP9, 13 s |
| `hero-loop.mp4` | ~15.0 MB | The supplied master, 720x1280, 31 s. Fallback only |
| `hero-poster.jpg` | ~31 KB | A frame captured at 13.5 s from the master |

The `<source>` order is WebM first, mp4 second: every current browser takes the
2.3 MB transcode, and the master is only reached by something without VP9.

**The WebM was produced in the browser, not by an encoder.** No ffmpeg was
available, so the master was drawn frame by frame into a 600x600 canvas —
already centre-cropped square, matching how the page renders it — and captured
with `MediaRecorder` at VP9 / 1.3 Mbps for 13 seconds from the 8 s mark. That
is the whole reason it now plays in a single-file build: 15 MB became 2.3 MB,
which base64-encodes to ~3.0 MB, comfortably inside the 16 MB page ceiling.

To redo it after replacing the master, run the transcode again from a served
copy of the page rather than hand-editing this file.

The clip replaced the engraved Corinthian-helmet plate in the hero. It is
portrait, so it is cropped square by `object-fit: cover` inside a circular
mask, and `mix-blend-mode: screen` drops its black ground out against the page
rather than sitting it in a hard-edged box. The light theme inverts and
multiplies instead, because a pale ground gives `screen` nothing to reveal.

`hero-poster.jpg` is the video's own first-choice frame, used three ways: as the
`poster` while the clip loads, as the reduced-motion still, and as the fallback
whenever the clip cannot play.

**The 15 MB master in Git is worth a decision.** It roughly doubles the
repository and every clone pays for it forever, since Git keeps all history —
and nothing actually loads it now that the WebM exists. Options, best first:

1. **Drop the master from Git.** Add `*.mp4` to `.gitignore` and keep it in
   shared storage. The WebM is the real asset and is only 2.3 MB; the mp4
   `<source>` can stay for the rare browser without VP9, or be removed
   outright.
2. Track it with **Git LFS** (`git lfs track "frontend/design/assets/*.mp4"`).
3. Keep it as an ordinary blob — the current state, and the costliest.


## Drop the team logo here

Save the Rokunin Sync logo as:

```
frontend/design/assets/rokunin-sync-logo.png
```

Transparent background, not the black-square version — the pages supply their own
ground and a baked-in black block will show as a rectangle on the light theme.
Roughly 1200px wide is plenty; it is never rendered above 220px.

If you also have the symbol on its own, without the wordmark, save it as:

```
frontend/design/assets/rokunin-sync-mark.png
```

Once either file exists the pages pick it up with no further edits — see
"How the swap works" below.

## Refinix and Rokunin Sync are different marks

Worth being deliberate about this, because the two get mixed up easily:

| | Name | Where it belongs |
|---|---|---|
| Repository | AegisForge | Git, internal only |
| Product | **Refinix** | Nav, page titles, the application UI |
| Team | **Rokunin Sync** | Credits, footer, the SIH deck |

The supplied lockup spells **ROKUNIN SYNC**, so it is the *team* mark. It is
placed in the footer credit and the closing signature, where team attribution
belongs. It is deliberately **not** used as the product wordmark in the nav — a
visitor downloading Refinix should see Refinix, not the team that built it.

The circular arrow **symbol** is name-neutral, so it works in both roles. It
currently stands in as the Refinix mark in the nav.

## How the swap works

`site.html` and `chat.html` currently draw the symbol as inline SVG
(`#rk-mark`), so the pages are complete without any binary asset. That is a
**stand-in**, drawn from the supplied logo — it is not the real artwork.

To swap in the real files:

1. Save the PNGs at the paths above.
2. In `site.html`, replace the `<svg class="mark">…</svg>` in `.nav-brand` with
   `<img class="mark" src="assets/rokunin-sync-mark.png" alt="">`.
3. In the footer credit and closing signature, the `<img class="team-logo">`
   elements already point at `rokunin-sync-logo.png` and are hidden until the
   file loads, so they appear on their own.

Single-file artifact builds inline anything under `assets/` as a `data:` URI
automatically, because published artifact pages cannot load external images.

## Licensing

Team-owned artwork. The four engraved plates in `site.html` are drawn in-repo
and carry no third-party licence. Do not add stock or scraped imagery here
without recording its licence in this file.
