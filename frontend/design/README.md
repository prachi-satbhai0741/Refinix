# Refinix design

Static design reference for the Refinix surfaces. Plain HTML and CSS with no
build step, matching the alpha delivery described in
[../README.md](../README.md): local files served by the coordinator, no frontend
build chain and no desktop wrapper.

**Status: design reference, not a wired surface.** These pages render fixed
sample markup. They do not connect to the coordinator, do not consume the event
stream, and nothing shown here is a measurement.

## Release claim boundary

These are visual references, including website and onboarding concepts, not the
shipped app or measured capabilities. Persistent Settings → Models uses the
[same lifecycle after onboarding](../../docs/model-catalog.md#persistent-model-management).
Website/download and PPT labels follow [PRD release bands](../../docs/prd.md#release-bands);
only [P14 publication acceptance](../../docs/releases.md#beta-01-publication) enables
a real Beta download. Keep the architecture vision visible and its evidence status
explicit. Existing dated visual decisions below remain reference history.

## Direction

Two treatments, chosen 2026-09-03 after a three-way comparison.

| Treatment | Where it applies |
|---|---|
| **Control Room** | Every application surface: Chat, Documents, Code, Control Center, onboarding, pairing |
| **Blueprint** | Artifacts only — generated documents, and the Proof Card |

**Control Room** takes its palette discipline from process-industry HMI
practice, where the normal state of the plant is grey and colour is spent only
where something is abnormal, measured, or absent. That is already the rule
[docs/security.md §12](../../docs/security.md) places on evidence display, so
the aesthetic and the requirement agree rather than compete.

**Blueprint** applies only to artifacts, because a generated approval note is a
document and is drawn as one. In light themes it is drafting vellum with ink
blue; in dark themes it becomes a cyanotype — a dark prussian ground with white
lines, which is what a blueprint physically is — rather than inverted paper.

Both themes are supported. Neither is the default: the bare `:root` carries the
complete light palette, `prefers-color-scheme` covers viewers on the system
default, and `[data-theme]` covers an explicit in-app choice.

### Application palette

Near-black ground, silver type, sky blue as the live accent, one green and one
purple. **Every colour has exactly one job, and the jobs do not overlap** —
which is what stops the palette from turning into decoration on a surface whose
whole purpose is to distinguish kinds of claim.

| Role | Job | Dark | Light |
|---|---|---|---|
| Silver | The resting state of everything. Most of the UI is this. | `#E8ECF2` `#A9B5C6` `#93A0B2` | `#0E141C` `#3E4959` `#4B5665` |
| Sky blue — `--signal` | Live: running now, focused, selected, awaiting you | `#6DB3F2` | `#1A5E97` |
| Green — `--st-enforced` | A named control is active, and completed marks | `#57C79A` | `#1A6349` |
| Purple — `--agent` | Provenance: this came from the model's own reasoning | `#B08CEC` | `#58399B` |
| Amber / red-clay | Caution, and fault | `#E8B96A` `#F0908A` | `#7A4C04` `#96322A` |

**Purple is the one addition that needed a job before it could be used.** It
marks *agent provenance* — the capability that ran a plan step in Chat or a
pipeline stage in Documents, and the plan's left rail. Provenance is not a state
claim, which is precisely why purple cannot be confused with enforced, observed
or unavailable. It is never used for status.

Green stays scarce: `--st-enforced` and the completed marks on a plan, pipeline
or job lifecycle. It is never decorative and never means *unavailable*, which is
grey and hatched by rule. One deliberate exception is documented in
`tokens.css`: the Code diff keeps conventional green/red for added and removed
lines, because that notation is older than this palette and readers know it.

`--brand` (the Rokunin Sync mark) now resolves to silver rather than orange, so
the mark sits inside the palette. It is still its own token, used in exactly two
places, so giving the mark a colour again is a one-line change.

### Geometry — what curves and what does not

`--radius` was previously declared and never used; everything was square by
omission. There is now a scale, and one rule decides where it applies:

> **Things you touch or talk to curve. Things you read as a measurement stay
> square.**

Buttons, chips, bubbles, the composer, nav items, cards, panels and dialogs
curve. Dense claim tables, diffs, run output, meters and the artifact document
do not — a readout is an instrument face, and rounding it makes it look like a
suggestion. `--radius-data: 0px` exists to make that deliberate rather than
accidental, and should stay 0.

The scale runs `--radius-xl` 26px (dialogs, the largest panels) → `--radius-lg`
18px (panels, cards) → `--radius` 13px (buttons, composer, containers) →
`--radius-sm` 9px (nav items, tags), with `--radius-bubble` 20px for a chat turn,
the most oval thing in the app.

Where a curved container holds square rows (`.rows`, `.pipe`, `.findings`,
`.tests`), the container carries the radius with `overflow: hidden` and the rows
inside stay square — so the panel stops looking like a spreadsheet without the
data losing its grid.

Two details worth keeping: the nav's active marker is an `inset box-shadow`
rather than a `border-left`, because a 2px border on a rounded box bows around
the corner instead of reading as a straight bar; and a chat turn tightens the
corner on the side it is anchored to, so the shape points back at whoever said
it.

### Glass

Glass only reads as glass when there is something behind it worth blurring, so
the app sits on three soft radial fields (`--atmo-*`) over the flat ground.
Without them every panel is flat translucent grey.

Glass is **spent, not spread**. One test decides it:

> **Is this thing floating over the canvas, with the ground or the conversation
> showing past its edges?**

Yes, so it earns glass: the header band, the composer *box*, the approval gate,
a dialog, the onboarding and pairing cards, and the floating controls (the panel
toggles and Jump to latest).

No, so it stays flat: **the nav and the rail**. They are full-height walls with
nothing moving behind them, and blurring them is what made the previous build
read as one washed sheet. They are now opaque `--surface-sunken` — darker than
the canvas, the way a chat application seats its sidebar.

Never, because you read them literally at 10–11px: the diff, the stdout/stderr
panes, the meters, dense claim tables, the artifact and the Proof Card.
Refracted ground behind small monospace costs legibility for nothing.

Two traps worth knowing:

- **The composer band is not the composer box.** The band is the full width of
  the window and ~120px tall, so glassing it puts a grey slab across the bottom
  of every screen. Glass goes on the object; the band stays the page.
- **A masked ancestor is a backdrop root.** `.thread` carries an edge mask, so a
  `backdrop-filter` on anything inside it — the user's message bubble, for
  instance — samples nothing and silently degrades to a flat translucent fill.
  The bubble takes an honest solid `--bubble-fill` instead.

`saturate()` stays near 100%. At 150% it multiplied every tint behind the glass,
which was one of the three things making the app read navy.

### Folding the walls

Both the nav and the rail fold away, from a three-line control at each end of
the surface header. `shell.js` drives it; `app.css` owns the appearance.

On a wide window the **grid track itself goes to zero**, so the middle column
genuinely gets the room. An overlay would cover the conversation rather than
widen it, which is the opposite of what the control is for. The panel fades in
120ms while the track takes 220ms, which hides the one frame where its contents
reflow at a narrow width, and its border goes transparent — a 1px border on a
zero-width track is still a 1px line.

Below their breakpoints (1180px for the rail, 760px for the nav) the same
control opens the wall as an **overlay with a scrim**, because at 375px there is
no room to give. This replaced `display: none`, which had silently deleted the
routing evidence and then the navigation itself with no way to ask for them
back.

The glyph reports state rather than naming an action: all three rules are full
width when the wall is open, and the middle rule retracts toward the window when
it is closed, mirrored per side.

The state is remembered per panel **per surface** — a collapsed rail on Chat
should not collapse it on Control Center, where it carries different evidence.
Storage is guarded in both directions; a blocked `localStorage` just means both
walls open.

> The overlay backdrop is `.panel-scrim`, **not** `.scrim`. `pairing.css`
> already owns `.scrim` for the always-visible backdrop behind the pairing
> dialog and declares neither `opacity` nor `visibility`, so a hidden-by-default
> `.scrim` leaked straight through it and hid the entire pairing flow.

**Two tiers, for cost rather than looks.** `--glass-*` carries the backdrop blur
and belongs to top-level surfaces; `--veil-*` is fill only, for containers
already sitting on a blurred parent. Blurring an already-blurred surface is
expensive and shows almost nothing, and this app puts a dozen panels on screen
at once.

`--glass-modal` is separate and much more opaque. A `.55` fill over a scrim
composites to a muddy mid-tone that dark text cannot hold 4.5:1 against — this
was a real failure in the pairing dialog, at 3.48:1, before the modal got its
own base and `--scrim` was tokenised so light stops dimming to near-black.

Two structural changes glass forced. The `gap: 1px` over an opaque parent trick
— used for the Documents sources and the onboarding plan totals — needs that
parent to be opaque, which blocks everything behind it. Both are now separated
cards with real gaps, which reads better anyway. And the light-mode atmosphere
had to be rebuilt: dark tints at 10% over a light ground *darken* it, which cost
contrast for dark text, so the light fields are near-white pastels that lift.

## Files

### Application — all six screens built

| File | Contents |
|---|---|
| `tokens.css` | Colour, type, spacing, geometry. Both themes. Load first |
| `app.css` | Shared shell: frame, nav, rail, chips, buttons, gate, artifact, tables |
| `chat.css` / `chat.html` | Chat — thread, plan steps, composer, execution target |
| `documents.css` / `documents.html` | Documents — sources, pipeline, findings, citations, validation |
| `code.css` / `code.html` | Code — file scope, diff, sandbox run, coordinator checks |
| `control.css` / `control.html` | Control Center — all eight groups from workflows §10 |
| `onboarding.css` / `onboarding.html` | First run, steps 1-3 — installation, main engine, capabilities |
| `onboarding-install.html` | First run, steps 4-5 — the stated plan, and the self-test |
| `pairing.css` / `pairing.html` | Pairing — code, both identities, terms, advertised capability |
| `shell.js` | The only script in the track: folds the nav and rail away. Loaded by the four application surfaces |

**Load order is always `tokens.css`, `app.css`, then the surface file.**
Anything shared between surfaces belongs in `app.css`; a surface file carries
only what is unique to it. The pages link to each other, so the set can be
clicked through as a whole — including into onboarding and pairing, which the
Control Center reaches through **Change setup**, **Re-run self-test**,
**Pair a device** and **Review and pair**.

`pairing.css` loads after `control.css`, because pairing is drawn as a dialog
over the Control Center rather than as a screen of its own.

Each surface is drawn from a specific workflow, not invented:

| Surface | Source |
|---|---|
| Chat | [workflows.md](../../docs/workflows.md) §4 |
| Documents | §5 — `inspection_report_to_approval_note` |
| Code | §6 — `repository_request_to_validated_patch` |
| Control Center | §10 — all eight required groups |
| Onboarding | §2 — first run, all five steps |
| Pairing | §8 — the trust exchange between two installations |

Three rules the surfaces exist to enforce, and where to see each one:

- **A finding never appears without its page.** Documents → extracted findings.
  The unresolved row keeps the extractor's own words and infers nothing.
- **The repository is not transferred.** Code → files in scope: the minimum
  relevant set, each with its hash.
- **No hard-coded healthy, secure, blocked or zero.** Control Center → every
  row names its enforcing layer or its observer, and a row with neither renders
  unavailable.
- **There are no silent downloads.** Onboarding step 4 states every action, its
  size, its licence and its checksum before anything is fetched, and the
  confirm box says what would have been unavailable had it failed.
- **A failed capability is reported, not hidden.** Onboarding step 5 ships with
  semantic knowledge unavailable — the embedding model installed, but no
  corpus path is configured — rather than showing seven green rows.
- **Pairing does not merge anything.** Pairing → *What pairing does*, where the
  three `[−]` rows carry as much weight as the three `[+]` rows.

### Public site

| File | Contents |
|---|---|
| `site.css` | Public site styles, including its own token block |
| `site.html` | Public site reference page |

`site.css` deliberately does **not** import `tokens.css`. The public site is a
different trust boundary and a different job, so it carries its own tokens and
does not inherit the application's instrument-panel restraint.

### Surface system

A black ground lit by four layered radial fields, with **glass panels**.
Nothing tiles and nothing rules the background.

**Palette — black, silver, sky blue, violet, green.**

| Role | Dark | Light |
|---|---|---|
| Ground / panel ground | `#070708` / `#0E0E10` | `#EEF1F5` / `#F7F9FB` |
| Text, silver tiers | `#F4F5F7` `#D3D6DA` `#9AA0A8` `#767C85` | `#0C1119` `#26313F` `#4A5665` `#5E6A78` |
| Metal ramp — `--silver-1..4` | `#FFFFFF` → `#5A616A` | inverted, `#5E666F` → `#171C22` |
| Interactive — sky blue | `#8CC2F2` | `#26618F` |
| Structure — violet | `#B497E8` | `#6742A8` |
| Enforced — green | `#74D2A6` | `#1E6B4F` |
| Team mark — the only orange | `#F08A24` | `#C96A0E` |

**The ground was blue-black and the page read navy.** Two things caused it
together, and fixing either alone would not have been enough. The raised tiers
were `#0D1017` and `#14181F` — blue-black rather than grey-black — and the
atmosphere layer sat a `rgba(46,108,178,.52)` blue field over the top of them.
The tiers now lift by luminance only, and no atmosphere field is above `.16`.

Colour discipline, one job each, and the jobs do not overlap:

| Colour | Means | Where |
|---|---|---|
| Sky blue | responds to a pointer | links, focus, hover, inline `code`, the *observed* state |
| Violet | indexes structure | section numerals, footer headings, formula operators, the *unavailable* state |
| Green | it actually happened | the *enforced* state, the shell prompt, completed steps, the zero-calls figure |
| Silver | struck metal | the mark, the wordmark, the stat figures, the formula terms |

The rule that keeps this legible is that **a numeral is not a link**, so the
numerals wear violet rather than the blue that means clickable. An earlier
amber-accented palette was rejected in review.

**The glass recipe** needs four things together; dropping any one flattens it:

```css
background: linear-gradient(180deg, rgba(255,255,255,.07), rgba(255,255,255,.022));
backdrop-filter: blur(34px) saturate(165%);
border: .8px solid rgba(255,255,255,.10);
box-shadow: inset 0 1px 0 rgba(255,255,255,.12),   /* top edge catches light */
            inset 0 -1px 0 rgba(255,255,255,.03),
            0 18px 44px rgba(0,0,0,.40);           /* lifts off the ground */
```

The gradient makes the surface catch light unevenly, the saturation lift keeps
colour alive behind the blur, the inset highlight reads as a polished edge, and
the outer shadow separates panel from ground.

The system is modelled on the surface treatment of contemporary agent-tool
sites — DeepSeek Harness and the Nous Hermes Agent page were the references the
requester named. What was taken is the technique: ground, lighting, glass,
radii, hairline borders, tabbed terminal blocks. Copy, branding, product
content and ornament are Refinix's own; the accent is the ember amber that
carries semantic weight in the application too.

Two earlier treatments were rejected in review and are recorded so they are not
retried: a tiled drafting grid (competed with the type, made the page look like
a form) and a single sparse plate (left the page feeling empty).

### Interaction

- **Surface switcher** — a window mock with Chat, Documents, Code and Control
  Center panels, so the page demonstrates the product rather than describing it.
- **Tabbed terminal blocks** with a copy button that strips prompts and comments.
- **Scroll reveal**, **hover lift** on cards, and a **theme toggle**.
- **Grain field** — a canvas of low-alpha particles behind the content. Two
  things make it Refinix's rather than generic: the whole field turns slowly
  about the viewport centre, which is the sync mark's motion at ambient scale,
  and roughly a fifth of the grains carry the brand orange. Grains brighten and
  scatter away from the pointer — measured at 5.4x peak alpha near the cursor
  against the far corner. Density and alpha were tuned against the reference
  implementation, which lights about 0.8% of its canvas at 0.04 alpha; this
  field sits near 0.5% because it is visible at rest rather than only on
  movement. Desktop pointers only, and skipped entirely under reduced motion.
  It replaced a pointer-tracked gradient spotlight, which read as a cheap
  flashlight effect.

Two failure modes were designed out rather than discovered later:

- Reveal styles apply only under a `.js` root class set by an inline bootstrap.
  Without that guard a script failure leaves the whole page invisible instead of
  merely unanimated.
- Reveal uses a scroll position check, **not** `IntersectionObserver`. An anchor
  jump moves elements past the viewport without crossing an intersection
  threshold, so an observer never fires for them and they stay at opacity 0
  permanently. The check also re-runs on `load` and `hashchange`, because the
  browser restores an anchor position after the script parses and a fragment
  jump emits no scroll event.
- Anything that must be correct rather than merely smooth runs **outside**
  `requestAnimationFrame`. The grain field paints one frame synchronously at
  init and repaints synchronously on resize, and the theme toggle recolours it
  synchronously — frames are throttled to zero in a background or hidden tab,
  so deferring correctness to rAF leaves the page in a stale state. Only the
  transition suppression, which is purely cosmetic, waits for a frame.

### The plates

Four engraved plates carry the ornament. The motifs are all Athena's, which is
not arbitrary: the aegis is her shield and the source of this repository's name,
the owl and the olive are her emblems, and the Parthenon is her temple.

| Plate | Where | Why there |
|---|---|---|
| Corinthian helmet, in a laurel and egg-and-dart medallion | Hero | The aegis — protection, and the repository's namesake |
| Athenian owl tetradrachm, with olive sprig and ΑΘΕ | Proof | A struck coin is a thing you verify rather than trust |
| Doric temple elevation | What it does | Standing on a foundation you own |
| Labyrinth of concentric circuits | Download | A sealed boundary with one path in |

All four are drawn as inline SVG rather than sourced. Artifact pages cannot load
external images at all, and drawn work carries no licensing question on a public
site — both of which rule out pulling an engraving off the web.

The dense ray field behind the hero medallion is a `repeating-conic-gradient`,
not markup: roughly a hundred spokes for one declaration, masked to an annulus
so the centre stays clean.

### Motion

Deliberately slow and few. Embers breathe behind the helmet's eye slots (3.4s),
the helmet and the owl blink on long offset cycles so a blink is noticed rather
than watched, the labyrinth carries one travelling glimmer, and the ray field
turns once every four minutes. All of it stops under
`prefers-reduced-motion`, with the embers left lit.

### The intro gate

The clip is portrait in a landscape window, so the gutters either side used to
sit flat black against a lit frame and the whole thing read as a video dropped
into a hole. The fix is an **ambient wash**: a 40x72 canvas takes a downscaled
copy of the current frame ten times a second, and is stretched and blurred
across the whole viewport behind the network field. The horizontal stretch is
the point — it drags the frame's own edge colour outward to meet the window, so
the screen reads as one surface. A short feather on the clip's vertical edges
removes the last hard line. Ten samples a second is nothing next to decoding
the clip a second time, which is the obvious alternative and much more
expensive.

The sequence after **Get started**: 1.0s of video glitch, then the figure holds
for **1.3s** under the storm, then it travels right onto its place in the page.

**The rays and the lightning have to be cancelled, not overridden.** An animated
property beats a plain declaration in the cascade, so
`.intro.exiting .eye { opacity: 0 }` never won and the rays kept firing through
the exit and the fade after it — the figure had gone and the light stayed. Both
now carry `animation: none !important` on exit, and both strikes are timed to
finish inside the hold rather than trailing past it.

### The page glitch is blocks, not slices

The figure on the page corrupts for ~0.5s every 3s. What makes it read as
*pixels* failing rather than film tearing is where the displacement comes from:
`#pixglitch` quantises its turbulence with `feFuncR/G type="discrete"`, so the
image is pushed around in flat blocks instead of flowing. Smooth turbulence
gives a liquid warp; stacked `clip-path` bands — the previous approach — slide
whole horizontal strips, which is a film artefact. Three things stack: block
displacement, a red/cyan channel split carried in the same filter, and a
stepped jitter so the figure snaps between positions instead of sliding. The
SVG animation is restarted with `beginElement()` each burst, or the pattern
would freeze and every burst would break up identically.

### The evidence rule

Set entirely in `--font-pixel` at the owner's request — label, heading, body and
all three claim cards. The sizes there run larger than the rest of the page and
the line-height is looser: a pixel face has a small x-height and no true italic,
and at the page's normal scale it reads markedly harder than the prose around
it. **This is the one section on the site set in a display face at body sizes;
if any legibility complaint arrives, this is where to look first.**

The drawn owl was replaced by a supplied motion clip. It is copied into
`assets/evidence-loop.mp4` **byte-for-byte** — `cmp` confirms it is identical to
the source, so there is no transcode and no generation of loss. It is paused
while off screen by an IntersectionObserver, because the page can have two clips
alive at once (this and the intro) and decoding both is what actually costs
frames. Under `prefers-reduced-motion` it gets controls instead of autoplay.

### Brand lockups

Two lockups, each used where its shape fits: **horizontal** (mark with the word
beside it) in the nav, where the bar is short and wide, and **stacked** (mark
over the word) on the intro gate and the closing signature, both of which have
room above and below.

**Both are drawn in the page, not loaded.** The supplied artwork was a raster on
a black square, which is the one thing that cannot be used on a page with a
light theme — the black block would show as a rectangle. So the mark is redrawn
as inline SVG (`#rfx-mark`) and the wordmark is set in Michroma, and both are
filled from the same brushed-steel ramp:

| Part | Fill | Note |
|---|---|---|
| Outer ring, three curved arrows | `url(#rfx-steel)` | highlight → shadow band → highlight |
| Inner pinwheel, three blades | `url(#rfx-steel-2)` | tilted against the first, so the two catch light at different angles |
| Wordmark | `.wordmark` gradient | same ramp, clipped to the text |

The two ramps are deliberately not the same gradient. One gradient across the
whole mark reads as flat foil; struck metal has faces at different angles, and
that is what the second ramp buys.

The mark geometry is **generated, not eyeballed** — arc endpoints and arrowhead
tips are computed so they actually meet. If the artwork changes, regenerate
rather than nudging path data by hand.

Sizing has one trap worth naming. `.lockup-mark` is sized in `em`, which works
in the nav because `.nav-brand` sets a font size — but the stacked containers
set none, so an `em` there pinned the mark to 16px while the wordmark beside it
scaled with `vw`. The stacked variants size in `clamp(px, vw, px)` instead.

**A real PNG still wins if one is produced.** Each lockup keeps an `<img>`
carrying `onerror="this.remove()"`, and `:has()` hides the drawn version *only
while that image is actually present*. Drop either file in and it takes over
with no further edits; leave them absent and the drawn lockup shows.

That hook costs **two 404s per page load** while the files are absent, which is
the price of a zero-edit swap. The rasters exist outside the repo, so the hook
is kept deliberately; if the decision is that the drawn lockups are final,
delete the two `<img>` elements and the `:has()` rules with them.

| File | Lockup | Used by |
|---|---|---|
| `assets/refinix-lockup-h.png` | mark + word beside it | nav |
| `assets/refinix-lockup-v.png` | mark over the word | intro gate, closing signature |

### The evidence section shows the states instead of describing them

The section carried three paragraphs explaining that an unavailable figure is
"drawn as absent — hatched, grey, and impossible to read as a healthy zero".
Prose describing a visual treatment is a sign the treatment is missing. It is
now one sentence, a three-line numbered rule, and three cards that *are* the
treatment: a continuous rail for enforced, a rail broken at the observation
interval for observed, and a dashed border over diagonal hatching for
unavailable. Roughly 120 words became 45, and the section says more.

Each card drives its rail, its tag and its source line from a single
`--state` custom property, so a state cannot end up half-recoloured.

The clip beside it was a bright graphic on a hard black ground inside a bordered
panel, which read as a black box on the page. It now blends with
`mix-blend-mode: screen` — but `.page` is `position:relative` with a `z-index`,
so it is a stacking context and the blend cannot reach the atmosphere behind it.
Screen alone therefore left the black ground exactly as it was. What removes the
box is **feathering the edge with a radial mask**; the interior black is `#000`
against a `#070708` page, a 3/255 difference that no one can see.

**The plates are placeholders.** The hero says so on its face, inside a marked
circle. Replace them with commissioned or public-domain artwork when a
direction is chosen.

The public site publishes no real build. No installer exists, so the download
section renders its honest pre-release state instead of a fabricated release.

**The sample-content strip across the top was removed** at the owner's request.
The substantive disclosure is unaffected — the *No public release yet* paragraph
still sits in the download section, where a visitor is actually deciding
something, and the nav still carries a **Pre-release** chip above the fold. If
that paragraph is ever softened, the strip should come back.

### The hero is sized to one screen

The whole hero has to be readable without scrolling: the terminal card at the
foot of the column and the entire figure both land above the fold. So the
section is sized from the viewport (`min-height: calc(100svh - var(--nav-h))`)
rather than from its content, and the two things that overflowed are capped by
viewport **height**, not just width:

- the headline is `clamp(2.4rem, min(6.6vw, 8.6vh), 6.2rem)` — a width-only
  clamp gave 99px on a 900px-tall window and pushed the terminal off the bottom;
- the figure is sized from its height on `.hero-plate`, not `.hero-art`, because
  the breathing fields are `::before`/`::after` on the plate and have to scale
  with it. A width-driven box made the figure 873px tall inside an 836px window.

Below `max-height: 800px` and `max-width: 1200px` the one-screen constraint is
released. There is genuinely not enough room for headline, lede, actions,
terminal card and a portrait figure at once on a short small screen, and forcing
it would only crush the type. Verified fitting at 1366×768, 1440×900, 1536×864,
1920×1080.

### The download section was removed

At the owner's request. Two things had to be handled rather than left to break:

- **The disclosure moved, it was not deleted.** *No public release yet* was the
  page's only substantive pre-release statement once the top strip went, and it
  lived inside the removed section. It now opens `.closing`, reworded — the old
  text pointed at "the builds below", which no longer exist.
- **The anchor was preserved.** Four links pointed at `#get` (nav, hero CTA,
  closing CTA, footer). `.closing` took `id="get"`, so all four still resolve and
  land on the section that states no build exists. Verified: zero dead anchors.

### Section order

Set by the owner, not by argument: hero → formula → **download** → design
approach → product → what it does → the evidence rule → counts → closing.
Download leads because the pre-release disclosure lives in it, so the page states
that no build exists before it describes anything.

### Page rhythm

Section spacing is one token, `--sec`, and every section pays it on the bottom
only — subsequent sections carry `padding-top: 0` inline. Get that wrong and the
junction doubles: `#proof` and `.closing` both did, giving 260px and 156px gaps
against a 130px rhythm, which is most of what read as empty page. `--sec` is now
`clamp(52px, 5.4vw, 92px)` and both junctions are closed, taking the document
from 8187px to 7538px at 1440.

`html { scroll-padding-top: 88px }` exists because the nav is sticky at
`top: 0`. Without it every in-page anchor landed with its own heading hidden
behind the bar.

Fonts load from Google Fonts in this reference. **A shipped offline build must
self-host them**, since [product invariant 1](../../docs/prd.md) forbids the
runtime depending on public network access. IBM Plex and Spectral are both
SIL OFL 1.1.

## Rules these pages follow

Taken from [docs/security.md §12](../../docs/security.md) and the frozen
contract in [backend/contracts/v1.py](../../backend/contracts/v1.py):

- **Enforced, observed, and unavailable are three different claims** and never
  share a colour. Enforced means a named control is active; observed means a
  named observer saw a count in a bounded window; unavailable means there is no
  evidence at all.
- **Absent evidence is never green and never red.** It renders grey, struck with
  a drawing hatch, so a missing observer cannot read as a healthy zero.
- **Every claim shows its source.** The contract's `NetworkEvidence` validator
  rejects a policy claim without an enforcer and counts without an observer, so
  the UI has no state in which it can honestly omit them.
- **State names come from the contract.** The lifecycle rail uses the `JobState`
  literals, the event log uses `Event.data.kind` values, and the approval gate
  carries an `Approval.action`. No page here invents a state the coordinator
  cannot emit.
- **The routing decision stays visible and overridable**, per
  [docs/prd.md §5](../../docs/prd.md).

## Verification performed

In Chromium, at a 1440 x 900 viewport. Each page was swept three times — once
per theme state — and the count below is the total of those three passes:

| Page | Element checks | Themes | Minimum contrast |
|---|---|---|---|
| `chat.html` | 336 | system dark, explicit dark, explicit light | 4.60:1 |
| `documents.html` | 555 | system dark, explicit dark, explicit light | 4.60:1 |
| `code.html` | 480 | system dark, explicit dark, explicit light | 5.01:1 |
| `control.html` | 723 | system dark, explicit dark, explicit light | 4.60:1 |
| `onboarding.html` | 432 | system dark, explicit dark, explicit light | 4.74:1 |
| `onboarding-install.html` | 261 | system dark, explicit dark, explicit light | 5.25:1 |
| `pairing.html` | 267 | system dark, explicit dark, explicit light | 5.01:1 |
| `site.html` | 322 | dark, light | 4.87:1 |

**3,054 element checks across the seven application pages, zero failures in any
theme state.**

**Glass required rewriting the auditor, and the rewrite found real bugs.** The
old one walked up the ancestor chain until it hit a background with alpha above
`.55` and used that — with glass, that colour is never what is actually on
screen. The current auditor alpha-composites every layer from the root down,
including the strongest `rgba` stop of each gradient, and computes the ratio
*twice*: once with gradient layers and once without, taking the lower. Neither
is universally the worst case, because a white-ish overlay lowers contrast for
light text and raises it for dark text.

That caught two failures the old auditor could not see: the pairing dialog at
**3.48:1** in light (a translucent modal over a heavy scrim), and the
`unavailable` hatch at **4.46:1**, where `--text-faint` crosses `--line-soft` —
the old walk stopped at the opaque row beneath and never looked at the hatch.
Both are fixed: `--glass-modal` and `--scrim` are their own tokens, and
`--line-soft` was lightened in light so the hatch reads as a drawing mark rather
than a bar.

The palette rebuild raised the floor from 4.53:1 to 4.74:1; glass gave a little
of that back, to 4.60:1, which is the honest number under a strictly
compositing measurement. `--agent` was checked before it was used — 6.98:1 in
dark and 5.92:1 in light on the grounds it lands on, at 10px, where the 4.5:1
threshold applies with no large-text exemption.

The light ground was deepened to `#D2D9E4` as part of the glass pass. Near-white
glass on a near-white ground collapses into one tone, and the panels stopped
reading as panels.

Four token values were raised across the earlier passes. `--st-fault` was 4.03:1
in dark and `--signal` was 4.49:1 on the sunken rail in light; `--st-unknown` was
4.43:1 on the light sunken ground; and `--text-faint` — fine on `--surface` —
fell to 4.06:1 on `--surface-raised`, which is what the model cards and the
pairing identity cards sit on. All four are structurally fixed in the current
palette rather than patched at the selector.

The public site was later swept with the same compositing auditor, which found
two failures the older measurement could not see: `--accent` at **4.14:1** on a
light glass panel, and `--ink-faint` at **4.18:1** on the artifact's raised
ground. Neither is related to the intro work — they were simply invisible to an
auditor that stopped at the first opaque ancestor. `--accent` was darkened and
`--ink-faint` lightened; the site now measures 4.87:1 light and 5.03:1 dark
across 184 elements per theme, with zero failures and no overflow.

- Contrast measured on every text-bearing element against its resolved
  background, not spot-checked. Six application token values were raised and
  the disabled target control recessed after the first sweep failed at 2.40:1.
- Fonts confirmed loaded rather than silently falling back, by measuring glyph
  widths against the fallback stacks.
- No horizontal overflow on any of the seven pages at 375, 768, 1024 or 1440.
  `chat.html` resolves to a 188 / 860 / 232 grid at 1280px.

**Measuring contrast across a theme swap needs care.** Elements with
`transition: color` report an interpolated or stale value, and a throttled tab
may not tick the transition at all — which looks exactly like the
"colour defined only inside a media query" bug but is not. Set
`data-theme-switching` on the root before measuring.

**A collapsed preview pane reports `clientWidth` 0**, which makes
`scrollWidth - clientWidth` look like hundreds of pixels of overflow on a page
that has none. Set an explicit viewport before trusting an overflow number.

Not verified: other browsers, screen readers, and keyboard traversal order.

## Still to build

The application design is complete. Chat, Documents, Code, Control Center,
onboarding and pairing are all built and cross-linked, covering workflows
sections 2, 4, 5, 6, 8 and 10.

These are design references, not an implementation. They carry sample data only:
no figure on any page is a measurement, and the pairing code is not a
credential. The one exception to "wired to nothing" is `shell.js`, which folds
the two walls away — real behaviour, but layout only; it reads and writes
nothing but its own `localStorage` key. Wiring the surfaces to the contract in
`backend/contracts/v1.py` is the next step, and belongs to whoever picks up the
frontend build.

Two smaller gaps remain inside what is built. Onboarding step 4 is drawn in its
confirmed state rather than mid-download, so there is no progress or failure
view for a fetch that stalls. Pairing is drawn at step 3 of 5; the revoke
confirmation is offered from the Control Center but not drawn.
