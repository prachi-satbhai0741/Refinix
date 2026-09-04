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


## The team logo

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

## The Refinix lockups are drawn, not stored

Two REFINIX lockups were supplied as rasters on a black square: **horizontal**
(mark then wordmark) and **stacked** (mark over wordmark). Neither is in this
directory, and that is deliberate rather than an omission.

A black-square raster is the one form the pages cannot use. The site has a light
theme, and a baked-in black block shows there as a rectangle — the same reason
this file already warns against the black-square version of the team logo. So
`site.html` draws both lockups instead:

| Piece | Where | How |
|---|---|---|
| Mark | `#rfx-mark` symbol in `site.html` | inline SVG, brushed-steel gradients |
| Wordmark | `.wordmark` in `site.css` | Michroma with the same ramp clipped to the text |
| Horizontal | `.lockup-h` | nav |
| Stacked | `.lockup-v` | intro gate, closing signature |

The drawn version scales cleanly, recolours for the light theme, costs no
bytes, and needs no binary in Git. `#rk-mark` remains as an alias of
`#rfx-mark`, because `chat.html` and the application surfaces reference the
symbol by that name.

### If you do want the rasters used

Save them at these paths and they take over with no code change:

```
frontend/design/assets/refinix-lockup-h.png
frontend/design/assets/refinix-lockup-v.png
```

Each lockup carries an `<img>` with `onerror="this.remove()"` above the drawn
version, and `:has()` hides the drawn version only while that image is actually
present. Export them with a **transparent** background, not the black square —
otherwise the light theme gets the rectangle this whole section is about.
Roughly 1200px on the long edge is plenty; neither is rendered above 220px.

The same applies to the team mark: `rokunin-sync-mark.png` (symbol alone) and
`rokunin-sync-logo.png` (full lockup) are picked up by the footer credit and
closing signature, which stay hidden until the file loads.

Single-file artifact builds inline anything under `assets/` as a `data:` URI
automatically, because published artifact pages cannot load external images.

## The sun ornament

`sun.png` — 736x736 RGBA, supplied artwork with the background already
removed. It sits in the band of empty page to the right of the Surfaces
heading, positioned absolutely so it costs no layout height. In normal flow
it made the page 203px taller, which defeats the point of an ornament whose
job is to fill a gap.

**The transparency is not optional.** The original was chrome on a white
ground, and no blend mode rescues a white ground on a black page: `multiply`
takes the whole thing to black, `screen` keeps the white. Any replacement
needs a real alpha channel — check the corner pixels rather than trusting
your eyes, since a viewer draws transparent and white identically.

It is dark chrome, so the dark theme lifts it slightly or the shadowed half
of every ray merges into the page; the light theme darkens it instead, where
the highlights are what disappear.

## Licensing

Team-owned artwork. The four engraved plates in `site.html` are drawn in-repo
and carry no third-party licence. Do not add stock or scraped imagery here
without recording its licence in this file.
