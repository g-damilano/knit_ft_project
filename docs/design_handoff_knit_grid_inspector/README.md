# Handoff: Knit Grid Catalog — Sample Inspector & Lattice Detection

## Overview
A desktop "instrument" workspace for cataloguing knit swatch scans. Operators import scans,
the system runs **lattice detection** to measure stitch gauge (needles & rows per 10 cm), and
the operator confirms/identifies each swatch before the catalog is delivered.

This handoff covers the **detail pane (Inspector)** and its **Lattice detection card**, which is
where most of the recent design work happened. The surrounding shell (title bar, toolbar, sample
queue on the left, run dock at the bottom) is included in the reference files for context.

## About the Design Files
The files in this bundle are **design references created in HTML/CSS + React-via-Babel** — runnable
prototypes that show intended look and behaviour, **not production code to ship as-is**. The Babel-in-
browser setup and `React.createElement` calls are a prototyping convenience. The task is to **recreate
these designs in the target codebase's environment** (e.g. a real React/TS app with a bundler, or
whatever framework the team uses), following its established component and styling patterns. If no
front-end environment exists yet, pick the most appropriate framework and implement there.

The detection/gauge values in the prototype are produced by a **mock** (`detectGauge` in `app.jsx`).
In production these come from the real image-analysis script — see **State Management → Data source**.

## Fidelity
**High-fidelity.** Final colours, typography, spacing, and interactions are intended to be matched
closely. All tokens are defined in `styles.css` (`:root`) and listed under **Design Tokens** below.
Recreate pixel-for-pixel using the codebase's libraries; keep the token values.

---

## Screens / Views

### Inspector (right detail pane)
Shown when ≥1 sample is selected in the left queue. Two modes:
- **Single** sample → identity header + detection card + metadata form.
- **Batch** (multi-select) → batch header; fields shared across the selection; differing values show a "Multiple" tag.

Vertical stack, scrollable, padding `22px 26px 28px`:

1. **Single header** (`.single-head`) — flex row, gap 18px, `margin-bottom: 22px`:
   - **Scan preview** (`.sh-preview`): fixed `172×130`, `border-radius 12px`, `overflow:hidden`. Contains:
     - `<img>` of the scan (object-fit: cover).
     - **Detected-lattice overlay** (`.grid-overlay`): absolutely positioned, **covers the right 34%** of the
       preview, `border-left: 1.5px solid rgba(255,255,255,0.7)`. It is a **white scrim behind a black grid**:
       a translucent white layer `rgba(255,255,255,0.5)` lightens the photo so the grid reads, and two
       `repeating-linear-gradient`s draw 1px grid lines in `rgba(26,26,28,0.62)`. **Cell size is driven by the
       gauge** via CSS vars `--cw` (column/wale spacing) and `--ch` (row spacing). See **Interactions → Grid overlay**.
       When the sample has no gauge yet, the overlay has class `.empty` (plain white scrim) and shows a
       monospace hint `"detect to\npreview grid"`.
     - **Badge** (`.badge-tl`) top-left: structure name (e.g. "plain / stockinette"), blurred translucent chip.
   - **Identity block** (`.sh-id`): breadcrumb "SAMPLE" + status chip; `<h2>` sample id (22px/600);
     file chips (scan filename, YAML sidecar or "no sidecar YAML"); a meta row (Machine / Structure / Gauge / Last run).

2. **Lattice detection card** (`.detect-card`) — see dedicated section below. This is the **first section of the
   Required group** (the section legend "REQUIRED — LATTICE GAUGE + SWATCH IDENTITY" sits above it).

3. **Scope bar** (`.scope-bar`): "Fields shown — N of M fields" on the left; a 2-option segmented control on the
   right: **Required** / **All fields**. Default **Required**.

4. **Metadata form** (`.fgrid`, 2-col grid, gap `14px 20px`): the editable fields, grouped by tier. See **Fields**.

5. **Form actions**: Save YAML / Attach / Reload / Reset buttons.

### Lattice detection card (`.detect-card`)
The headline component. `border: 1px solid var(--border)`, `radius 12px`, `padding 16px`. If detection
failed/low-confidence, add `.alert` (warm border + `--warn-soft` background).

- **Head** (`.detect-head`): grid icon in an accent tile; title "Lattice detection"; sub-description that changes
  with state; a **status chip** on the right (Not detected / Detecting… / Detected / Check needed / Manual).
- **Body** (`.detect-body`): the **gauge inputs** — `Needles / 10 cm` ✕ `Rows / 10 cm` (numeric, mono, with unit
  suffixes "wales"/"rows"), then a **Detect lattice / Re-detect** button (primary when unset, subtle once settled).
- **Readouts** (`.detect-readouts`): a `1.4fr 1fr 1fr` grid, 2 rows, gap `18px 16px`. These are **script-derived and
  read-only**, except Axis order:
  - **Axis order (x / y)** — the only editable readout: a segmented control with two options `needle / row` and
    `row / needle`. "Defined once per scan; flip if axes came out swapped."
  - **Gauge source** — auto: `image analysis` (from detection) or `manual entry` (after a hand edit). Read-only.
  - **Measurement state** — auto: `measured`. Read-only.
  - **Needle period** — computed `10 ÷ needles` cm. Read-only.
  - **Row period** — computed `10 ÷ rows` cm. Read-only.
  - **Confidence** — numeric script score shown as a percentage (e.g. `96%`). Read-only.

Each readout label carries an **info (i) dot** (see Interactions → Info tooltips).

---

## Fields (metadata schema)
Schema lives in `data.jsx` (`FIELDS`). Two tiers: `required` and `optional`. The **Required** scope shows only
required fields; **All fields** shows both groups. Gauge, axis order, confidence, gauge source and measurement
state are **owned by the detection card** (listed in `DETECTION_KEYS`) and are NOT rendered in the form grid.

**Required (identity — a measured gauge is meaningless without the swatch identified):**
`sample_id` (Sample ID), `yarn_ref` (Yarn), `tension_ref` (**Carriage tension**), `yarn_tension` (Yarn tension),
`machine_ref` (Machine, select), `bed_setup` (Bed setup, select), `structure_ref` (Structure, select).
Plus the detection-owned required keys: `needles_per_10cm`, `rows_per_10cm`, `measurement_state`, `gauge_source`.

> NOTE: the old **Source image** editable field was **removed**. The scan filename is still shown read-only in the
> identity header's file chip; it is no longer an editable form field.

**Optional / advanced:**
`weighting_ref` (Weighting, numeric, unit **g/needle**), `dye_lot` (Dye lot), `fibre_composition` (Fibre composition, full width),
`yarn_count` (**Yarn count** — grist, e.g. `2/30`), `thread_count` (**Thread count** — number of strands held together, numeric, unit "strands"),
`colour_ref` (Colour), `notes` (Notes, textarea, full width). Plus detection-owned `axis_order` and `confidence`.

Field control types: `text`, `num` (with optional `unit`, `mono`), `select` (options in `OPTS`), `seg` (segmented),
`textarea`. `span: true` makes a field full-width in the 2-col grid.

---

## Interactions & Behavior

### Grid overlay (gauge-driven lattice preview)
- Covers the **right 34%** of the scan preview.
- Cell width `--cw` and height `--ch` are computed from the gauge with a **single px/cm scale** so the wale/row
  aspect is faithful: `cw = clamp(6, 40, 460 / needles)`, `ch = clamp(6, 40, 460 / rows)` (px).
- **Updates live** as the operator edits Needles/Rows in the detection card (the header re-renders from the same
  sample state). Fewer needles → wider columns; fewer rows → taller cells.
- No gauge yet → `.empty` (white scrim only) + hint text.

### Detection
- **Detect lattice / Re-detect** runs detection for the selected sample(s). While running, the chip shows a spinner
  ("Detecting…"); on completion the gauge + readouts populate and a toast confirms (or warns on low confidence).
- New/imported scans auto-run detection on import.

### Manual gauge edit
- Typing into Needles or Rows by hand flags the sample: chip → **Manual**, `gauge_source` → **manual entry**,
  `measurement_state` → **measured**, internal `manual_override` → on. (There is **no** manual on/off toggle —
  it is derived state.)

### Info tooltips ("i" dots)
- Small 14px circular "i" button next to field labels and readout labels (`.info-dot`).
- On **hover OR keyboard focus**, a tooltip (`.info-pop`) appears below the dot with a plain-language explanation.
- The tooltip is **rendered to a top layer (portal to `<body>`), position: fixed**, so it is never clipped by the
  scrolling inspector. It is horizontally clamped to stay within the viewport (`translateX(-50%)`, left clamped to
  `[140, innerWidth-140]`), `max-width 250px`. Dark box (`var(--text)` bg, `var(--surface)` text). Dismiss on
  mouse-leave / blur / second click.
- The explanatory copy for every key is in `data.jsx` → `INFO` (keyed by field key, plus `needle_period`/`row_period`).

### Scope filter
- Segmented control **Required / All fields**; toggles whether the optional group renders. Counter shows
  "N of M fields".

### Batch editing
- With multiple samples selected, fields show shared values; differing values render a **"Multiple"** tag and the
  control is in a mixed state. Editing a field writes to all selected samples.

---

## State Management
Per-sample object (see `makeSample` / `SEED` in `data.jsx`). Key fields:
- Gauge: `needles_per_10cm`, `rows_per_10cm` (strings).
- Detection-derived: `axis_order` ("needle / row" | "row / needle"), `confidence` (decimal string 0–1, shown as %),
  `gauge_source`, `measurement_state`, `detect_state` (`""|detecting|detected|failed|manual`), `manual_override`.
- Identity: `sample_id`, `yarn_ref`, `tension_ref`, `yarn_tension`, `machine_ref`, `bed_setup`, `structure_ref`.
- Optional: `weighting_ref`, `dye_lot`, `fibre_composition`, `yarn_count`, `thread_count`, `colour_ref`, `notes`.
- Bookkeeping: `source_image_name` (read-only display), `status`, `hasYaml`, `yamlName`, `elapsed`, `progress`.

`status` is recomputed: a sample is `needs` if any **required** key is empty, else `ready` (run states override).

### Data source (production)
Replace `detectGauge()` (mock in `app.jsx`) with the real image-analysis result. It must return at least:
`needles_per_10cm`, `rows_per_10cm`, `axis_order`, `confidence` (0–1), and set `gauge_source: "image analysis"`,
`measurement_state: "measured"`, `detect_state: "detected" | "failed"`. Needle/row **period (cm)** are derived in
the UI (`10 ÷ count`), not stored.

---

## Design Tokens
All in `styles.css` `:root` (light) and `[data-theme="dark"]`. Highlights:
- **Neutrals (faint warm white):** `--bg oklch(0.983 0.0025 90)`, `--surface #fff`, `--surface-2/3`, borders `--border`/`--border-strong`.
- **Text:** `--text oklch(0.24 0.010 75)`, `--text-muted oklch(0.505 …)`, `--text-faint oklch(0.66 …)`.
- **Accent (teal, hue-swappable via `--accent-h`, default 175):** `--accent oklch(0.52 0.085 h)` + hover/press/soft variants.
- **Status:** `--warn`/`--warn-text`, `--danger`, `--success`, `--info` (+ `-soft` fills).
- **Radius:** `--radius 8`, `--radius-sm 6`, `--radius-lg 12`. **Shadows:** `--shadow-1/2/3`.
- **Type:** `--font-sans "IBM Plex Sans"`, `--font-mono "IBM Plex Mono"`. Base 14px / line-height 1.45.
- **Grid overlay specifics:** scrim `rgba(255,255,255,0.5)`, grid lines `rgba(26,26,28,0.62)`, width 34%, cell scale `460`.
- Density (`[data-density="compact"]`) and UI scale are user-tweakable; honour them or drop if out of scope.

## Assets
- Scan thumbnails are generated procedurally in the prototype (`swatch.jsx` → `thumbFor`). In production, use the real
  scan images. The reference cover `composed_catalog_cover.png` (from the user) shows the intended look of the
  right-third grid overlay + white scrim.
- Icons: inline SVG set in `icons.jsx`. Fonts: IBM Plex Sans/Mono (Google Fonts, loaded in `index.html`).

## Files (in this bundle)
- `index.html` — entry; font + script loading; React/Babel pins.
- `styles.css` — all tokens and component styles.
- `data.jsx` — schema (`FIELDS`, `OPTS`, `TIERS`, `INFO`), `makeSample`, seed data.
- `inspector.jsx` — **the focus of this handoff**: Inspector, SingleHeader (grid overlay), DetectionCard,
  DetectReadouts, InfoTip, MetadataForm, ScopeBar.
- `app.jsx` — app shell, selection, mock detection (`detectGauge`), toasts, tweaks, run simulation.
- `queue.jsx`, `dock.jsx`, `icons.jsx`, `swatch.jsx`, `tweaks-panel.jsx` — supporting UI for context.
