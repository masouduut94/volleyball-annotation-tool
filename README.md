# Volleyball Annotation Platform

A desktop annotation tool for volleyball video and image datasets. It combines
frame-level object annotation (court, players, ball, actions) with
video-level temporal annotation (service / in-play / no-play game states),
AI-assisted pre-labeling (YOLO detectors + a VideoMAE classifier), and
one-click dataset export for both model families.

<p align="center">
  <img src="docs/images/banner.png" alt="Volleyball Annotation Platform — main window" width="850">
</p>

> 📸 **Where to put screenshots:** every image referenced in this README
> lives under [`docs/images/`](docs/images). Create that folder if it
> doesn't exist yet, and save each screenshot using the **exact filename**
> called out in the section below it — the README already links to those
> paths, so dropping in a correctly-named file is all that's needed to make
> it render. See [Screenshots Checklist](#screenshots-checklist) for the
> full list in one place.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Key Features](#2-key-features)
3. [Annotation Concepts](#3-annotation-concepts)
4. [Getting Started](#4-getting-started)
   - [4.1 Requirements](#41-requirements)
   - [4.2 Installation](#42-installation)
   - [4.3 Running the Application](#43-running-the-application)
5. [User Interface](#5-user-interface)
   - [5.1 Main Window](#51-main-window)
   - [5.2 Top Toolbar](#52-top-toolbar)
   - [5.3 Left Sidebar](#53-left-sidebar)
   - [5.4 Right Sidebar / AI Panel](#54-right-sidebar--ai-panel)
   - [5.5 Bottom Toolbar](#55-bottom-toolbar)
6. [Working with Images and Videos](#6-working-with-images-and-videos)
   - [6.1 Open Images](#61-open-images)
   - [6.2 Open Video](#62-open-video)
   - [6.3 Frame Navigation](#63-frame-navigation)
   - [6.4 Playback](#64-playback)
7. [Frame-Level Annotation](#7-frame-level-annotation)
   - [7.1 Court Annotation](#71-court-annotation)
   - [7.2 Player Annotation](#72-player-annotation)
   - [7.3 Ball Annotation](#73-ball-annotation)
   - [7.4 Action Annotation](#74-action-annotation)
8. [Video-Level / Temporal Annotation](#8-video-level--temporal-annotation)
   - [8.1 Temporal Labels](#81-temporal-labels)
   - [8.2 Starting and Ending a Label](#82-starting-and-ending-a-label)
   - [8.3 Timeline](#83-timeline)
   - [8.4 Editing Temporal Annotations](#84-editing-temporal-annotations)
9. [AI-Assisted Annotation](#9-ai-assisted-annotation)
   - [9.1 Model Configuration](#91-model-configuration)
   - [9.2 Ball / Player / Action Detection (YOLO)](#92-ball--player--action-detection-yolo)
   - [9.3 Game State Classification (VideoMAE)](#93-game-state-classification-videomae)
   - [9.4 Batch Inference](#94-batch-inference)
10. [Annotation Status & Statistics](#10-annotation-status--statistics)
    - [10.1 Per-Layer Status Panel](#101-per-layer-status-panel)
    - [10.2 Confirming a Frame](#102-confirming-a-frame)
    - [10.3 Annotation Statistics Dialog](#103-annotation-statistics-dialog)
11. [Annotation Database](#11-annotation-database)
12. [Exporting Annotations](#12-exporting-annotations)
    - [12.1 YOLO Export](#121-yolo-export)
    - [12.2 VideoMAE Export](#122-videomae-export)
13. [Keyboard Shortcuts](#13-keyboard-shortcuts)
14. [Project Structure](#14-project-structure)
15. [Configuration](#15-configuration)
16. [Development](#16-development)
17. [Contributing](#17-contributing)
18. [License](#18-license)
19. [Screenshots Checklist](#screenshots-checklist)

---

## 1. Overview

The Volleyball Annotation Platform is a PyQt6 desktop application built to
produce two different kinds of training data from the same source
footage:

- **Frame-level annotations** — bounding boxes and polygons for the court,
  players, ball, and player actions (spike, block, set, receive), stored
  per (media, layer, frame) and exportable as a YOLO dataset.
- **Video-level annotations** — temporal segments describing the game
  state (`service`, `play`, `no-play`) across a range of frames, either
  tagged by hand or produced by a VideoMAE video classifier, and
  exportable as a clip dataset for retraining that classifier.

A single SQLite database (via SQLAlchemy) backs both annotation types, so
the same video can carry frame-level boxes and temporal game-state tags
side by side.

## 2. Key Features

- Two annotation workflows in one app: per-frame object annotation and
  temporal video-segment tagging, each with its own tab in the left
  sidebar.
- AI-assisted pre-labeling: YOLO models for ball / players / actions, and
  a VideoMAE classifier for game state, both configurable from the UI.
- A zoomable **Temporal Timeline** with per-label rows, drag-to-move /
  drag-to-resize intervals, and batched apply/cancel of edits.
- Per-layer annotation status tracking (`None` / `AI` / `User` /
  `Confirmed`) with one-click confirmation, visible for all four frame
  layers at once.
- Undo/redo for manual edits, with AI imports and confirmations tracked
  separately from freehand drawing.
- One-click dataset export for both model families — YOLO (detection or
  segmentation, with augmentation and train/val split) and VideoMAE
  (frame-clip dataset with weighted random sampling and augmentation).
- A built-in annotation statistics dialog (bar chart / pie chart) showing
  counts per layer and label across the whole dataset.

## 3. Annotation Concepts

| Term | Meaning |
|---|---|
| **Layer** | A category of frame-level annotation: `court`, `players`, `ball`, `actions`. Each layer has its own set of labels and its own annotation review status per frame. |
| **Label** | A specific class within a layer, e.g. `net` (court), `player` / `libero` / `referee` (players), `ball`, or `spike` / `block` / `set` / `receive` (actions). |
| **Annotation** | One drawn shape (rectangle or polygon) for a given media file, layer, label, and frame number. |
| **Game state** | The temporal label for a range of video frames: `service`, `play` ("in-play"), or `no-play`. |
| **Segment** | A `(start_frame, end_frame, state)` triple stored for a video, either `source="manual"` (hand-tagged) or `source="model"` (VideoMAE output). |
| **Confirmation** | A human sign-off that every annotation for a given (media, layer, frame) has been reviewed. Adding new AI detections resets confirmation for that layer/frame. |

## 4. Getting Started

### 4.1 Requirements

- Python 3.10+
- PyQt6
- OpenCV (`opencv-python`)
- SQLAlchemy
- `dataclasses-json`
- `torch` + `transformers` (for the VideoMAE game-state classifier)
- A YOLO-compatible detection/segmentation library for the frame-level
  auto-annotators (e.g. `ultralytics`)

> Pin exact versions in `requirements.txt` for your environment — add one
> if this repo doesn't have it yet.

### 4.2 Installation

```bash
git clone <repository-url>
cd <repository-folder>
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 4.3 Running the Application

```bash
python main.py
```

On first launch, the app creates a SQLite database (`annotations.db` by
default) and seeds it with the default layers/labels described in
[Section 3](#3-annotation-concepts).

## 5. User Interface

### 5.1 Main Window

The main window is split into four regions: the **top toolbar** (file
operations and export), the **left sidebar** (annotation controls, tabbed),
the central **graphics view** (the current frame/image), the **right
sidebar** (AI tools and annotation status), and the **bottom toolbar**
(frame navigation and playback), with the collapsible **Temporal Timeline**
docked beneath it once a video is loaded.

```
docs/images/main-window-overview.png
```
*Save a full-window screenshot here, ideally with a video loaded so the
Temporal Timeline is visible at the bottom.*

### 5.2 Top Toolbar

Open Images, Open Video, Clear, Save, and an **Export** menu (YOLO and
VideoMAE — see [Section 12](#12-exporting-annotations)).

### 5.3 Left Sidebar

Two tabs:

- **Frame Annotations** — layer selector, label selector, and drawing
  tool (rectangle / polygon / selection).
- **Video Annotations** — game-state label rows (Service / In-Play /
  No-Play), and the Mark Start → Mark End workflow for hand-tagging a
  temporal segment.

```
docs/images/left-sidebar-frame-tab.png
docs/images/left-sidebar-video-tab.png
```
*Two screenshots: one with the Frame Annotations tab active, one with
Video Annotations active (ideally mid-tag, showing the "Mark End" button
state).*

### 5.4 Right Sidebar / AI Panel

From top to bottom: **Object Detection** rows (Ball / Players / Actions,
each with a status indicator, a "…" model-path button, and a Run button),
the **Game State (Video)** row (model path + a **Range…** button that
opens the classification-range dialog), the **Annotation Status** table
(one row per layer, with a colored status badge and a Confirm button),
and the **Quick Annotate** button that opens batch inference.

```
docs/images/right-sidebar.png
```
*Screenshot of the full right sidebar, showing all sections: Object
Detection rows, the Game State row, the Annotation Status table, and the
Quick Annotate button.*

```
docs/images/game-state-range-dialog.png
```
*Screenshot taken right after clicking the **Range…** button on the Game
State row — capture the "Classify Game State" dialog with its Start
frame / End frame / Window size fields visible.*

### 5.5 Bottom Toolbar

Previous/Next frame, ±15-frame jumps, Play/Pause, a color-coded seek bar
(segments painted by game state), a frame number spinner, and the total
frame count.

## 6. Working with Images and Videos

### 6.1 Open Images

**Top Toolbar → Open Images** lets you select one or more image files.
They're treated as an ordered sequence you can step through like frames.

### 6.2 Open Video

**Top Toolbar → Open Video** loads an `.mp4` / `.avi` / `.mov` / `.mkv`
file. The Temporal Timeline becomes visible and is sized to the video's
frame count and fps.

### 6.3 Frame Navigation

`A` / `D` step one frame back/forward; `Q` / `E` jump 15 frames; the
bottom-toolbar slider, spin box, and Temporal Timeline ruler all seek
directly to a frame.

### 6.4 Playback

`Space` toggles play/pause for a loaded video, at the video's native fps
(or 30 fps as a fallback if it can't be read).

## 7. Frame-Level Annotation

Select a layer and label in the **Frame Annotations** tab, pick a tool
(`R` rectangle / `P` polygon / `Esc` selection), and draw directly on the
frame. `Ctrl+Z` / `Ctrl+Shift+Z` undo/redo; `Shift+Delete` clears every
annotation in the current layer for the current frame.

### 7.1 Court Annotation

Layer `court`: labels `net`, `attack zone`, `back zone`.

### 7.2 Player Annotation

Layer `players`: labels `player`, `libero`, `referee`.

### 7.3 Ball Annotation

Layer `ball`: label `ball`.

### 7.4 Action Annotation

Layer `actions`: labels `spike`, `block`, `set`, `receive`.

## 8. Video-Level / Temporal Annotation

### 8.1 Temporal Labels

Three fixed game-state labels: **Service**, **In-Play**, **No-Play**,
selected from the **Video Annotations** tab in the left sidebar (cycle
between them with `Alt+3`).

### 8.2 Starting and Ending a Label

Click **Mark Start** at the first frame of the segment — the button
becomes **Mark End**, and a live, growing rectangle appears in that
label's row on the Temporal Timeline as you scrub forward. Nothing is
written to the database until **Mark End** is clicked; **Cancel**
discards the in-progress tag entirely.

### 8.3 Timeline

The Temporal Timeline (docked under the bottom toolbar, collapsible) shows
one row per label, a frame-number ruler on top and a time (`mm:ss.ff`)
ruler on the bottom, a draggable playhead, and horizontal zoom via the
slider in its header.

```
docs/images/temporal-timeline.png
```
*Screenshot of the Temporal Timeline with a few segments visible across
all three rows, ideally including one segment mid-drag (dashed yellow
outline) to show the pending-edit state.*

### 8.4 Editing Temporal Annotations

Drag a segment's body to move it, or its edges to resize it — edits are
**batched**: dragged segments get a dashed outline, and nothing is saved
until you click **Apply Changes** (or hit `Ctrl+S`, which also flushes
pending timeline edits). **Cancel Changes** reverts every dragged segment
back to its last-saved position. **Delete Selected** removes the
currently selected segment immediately.

## 9. AI-Assisted Annotation

### 9.1 Model Configuration

Each AI tool (Ball, Players, Actions, Game State) has its own **"…"**
button in the right sidebar to point it at a local model file (`.pt` /
`.onnx` for YOLO models, a folder for the VideoMAE checkpoint). A ✓ or !
badge shows whether each model is currently configured.

### 9.2 Ball / Player / Action Detection (YOLO)

Click **Run** on a detection row to run that model on the current frame
and import any detections whose class names match the active layer's
labels. Imported detections are flagged `is_ai_generated=True` and reset
that layer/frame's confirmation status.

### 9.3 Game State Classification (VideoMAE)

Click **Range…** on the Game State row to open the classification dialog,
choose a start/end frame range and a window size, and run the classifier
over that range in the background. Consecutive windows that resolve to
the same state are automatically merged into a single segment (so a 5
second in-play stretch becomes one segment instead of five 1-second
ones), then written to the Temporal Timeline as `source="model"` segments.

### 9.4 Batch Inference

**Quick Annotate** (or `Ctrl+Shift+A`) opens a dialog to run one or more
YOLO detectors across a range of frames/images in one background job,
rather than one frame at a time.

## 10. Annotation Status & Statistics

### 10.1 Per-Layer Status Panel

The **Annotation Status** table in the right sidebar shows, for the
*current frame*, one row per layer with a colored badge:

| Status | Meaning | Color |
|---|---|---|
| `None` | No annotations exist for this layer/frame | Grey |
| `AI` | Annotations exist and at least one is AI-generated, not yet reviewed | Yellow |
| `User` | All annotations were hand-drawn | Blue |
| `Confirmed` | A human has explicitly signed off on this layer/frame | Green |

### 10.2 Confirming a Frame

Click **Confirm** on any row to sign off that layer for the current
frame, or press `Ctrl+K` to confirm whichever layer is currently active
in the Frame Annotations tab.

### 10.3 Annotation Statistics Dialog

Open via `Ctrl+Shift+S` (or a toolbar button, if wired up in your build).
Shows dataset-wide annotation counts per layer/label as a grouped bar
chart or a pie chart, plus an exact-numbers table.

```
docs/images/annotation-stats-dialog.png
```
*Screenshot of the statistics dialog, ideally with the bar chart view
selected and a few layers/labels populated.*

## 11. Annotation Database

All data is stored in a single SQLite file via SQLAlchemy
(`database/schema.py` / `database/db.py`):

- `layers` / `labels` — the fixed layer/label taxonomy.
- `media` — one row per opened image or video.
- `annotations` — frame-level shapes, with `is_ai_generated` and
  `confirmed` flags.
- `frame_reviews` — per (media, layer, frame) human confirmation state.
- `model_configs` — saved model file/folder paths per AI tool.
- `game_state_segments` — temporal segments, with a `source` column
  (`"manual"` or `"model"`).

## 12. Exporting Annotations

### 12.1 YOLO Export

**Top Toolbar → Export → YOLO** opens a dialog to configure:

- **Export mode** — combined or separate datasets.
- **Annotation format** — detection (bounding boxes) or segmentation
  (polygons).
- **Layers & labels** — pick exactly which layers/labels to include.
- **Videos / media** — pick which annotated media files to pull from.
- **Augmentation** — random brightness/contrast, color jitter, and/or
  horizontal flip; each adds an extra augmented copy per image.
- **Validation split** — a percentage held out as a validation set.

Export runs in the background with a progress dialog, and finishes with a
summary (annotation counts, image counts, train/val split).

### 12.2 VideoMAE Export

**Top Toolbar → Export → VideoMAE** builds a frame-clip dataset for
retraining the game-state classifier, from the temporal segments already
stored in the database:

- **Videos** — pick which annotated videos to draw clips from.
- **Frames per clip** — the fixed clip length every exported clip is
  resampled to.
- **Service clips** — every stored `service` segment becomes exactly one
  clip; service periods are short and scarce, so none are skipped or
  sub-sampled.
- **In-Play / No-Play clips** — a requested clip count is filled by
  drawing random windows from anywhere inside the stored segments for
  that state, weighted by segment length (longer segments contribute
  proportionally more candidate windows).
- **Augmentation** — random brightness/contrast, horizontal flip, and/or
  RGB channel manipulation; each adds one augmented copy per clip.

Output is a folder of per-clip frame images (`service/`, `play/`,
`no-play/`) plus a `manifest.csv` listing every clip's source video,
frame range, state, and augmentation variant.

```
docs/images/yolo-export-dialog.png
docs/images/videomae-export-dialog.png
```
*One screenshot per export dialog, showing their respective configuration
options filled in.*

## 13. Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `A` / `D` | Previous / next frame |
| `Q` / `E` | Previous / next 15 frames |
| `Space` | Play / pause video |
| `Ctrl+S` | Save annotations (also flushes pending timeline edits) |
| `Shift+Delete` | Clear current frame's annotations (active layer) |
| `Ctrl+Shift+A` | Open batch inference (Quick Annotate) |
| `Ctrl+Z` / `Ctrl+Shift+Z` | Undo / redo |
| `Ctrl+K` | Confirm current frame (active layer) |
| `Esc` | Switch to selection tool |
| `P` / `R` | Polygon / rectangle tool |
| `Alt+1` | Cycle frame-annotation layer |
| `Alt+2` | Cycle frame-annotation label |
| `Alt+3` | Cycle video-annotation (game-state) label |
| `Ctrl+Shift+S` | Open annotation statistics dialog |

## 14. Project Structure

```
.
├── main.py
├── main_window.py
├── graphics_view.py
├── graphics_scene.py
├── database/
│   ├── db.py                    # DatabaseManager — all queries/writes
│   ├── schema.py                 # SQLAlchemy ORM models
│   └── data.py                   # Plain dataclasses used across the app
├── services/
│   ├── auto_annotator.py         # YOLO model wrapper (ball/players/actions)
│   ├── game_state_classifier.py  # VideoMAE wrapper
│   ├── game_state_worker.py      # Background AI game-state classification
│   ├── batch_inference.py        # Multi-frame / multi-model batch job
│   ├── yolo_export_worker.py     # Background YOLO dataset export
│   └── videomae_export_worker.py # Background VideoMAE clip export
├── ui/
│   ├── top_toolbar.py
│   ├── left_sidebar.py           # Frame Annotations + Video Annotations tabs
│   ├── right_sidebar.py          # AI panel + Annotation Status table
│   ├── bottom_toolbar.py
│   ├── temporal_timeline.py      # Temporal Timeline widget
│   ├── game_state_dialog.py      # AI classification range dialog
│   ├── export_dialog.py          # YOLO export dialog + summary
│   ├── export_tooltip_texts.py
│   ├── export_progress_dialog.py
│   ├── videomae_export_dialog.py # VideoMAE export dialog
│   ├── annotation_stats_dialog.py
│   └── utils.py                  # Shared widgets/helpers (tooltips, buttons, etc.)
└── docs/
    └── images/                   # <- put every README screenshot here
```

## 15. Configuration

Model paths, once set via the right sidebar's "…" buttons, persist in the
`model_configs` table — no separate config file to edit. The database
path itself is passed to `MainWindow(db_path=...)` in `main.py` and
defaults to `annotations.db` in the working directory.

## 16. Development

```bash
# run with a scratch database so you don't touch real annotations
python main.py --db-path dev.db   # adjust to however main.py exposes this
```

Contributions to the auto-annotator/classifier wrappers should keep the
model-specific logic isolated (see `game_state_classifier.py`'s docstring)
so swapping a backbone doesn't ripple through the rest of the app.

## 17. Contributing

1. Fork the repo and create a feature branch.
2. Keep UI changes consistent with the existing dark theme and widget
   patterns (see `ui/utils.py` for shared helpers).
3. Open a pull request describing the change and, where relevant, attach
   a screenshot or short clip.

## 18. License

Add your license here (e.g. MIT, Apache 2.0) — none specified yet.

---

## Screenshots Checklist

Save every file below under `docs/images/` using these exact names so the
links throughout this README resolve automatically:

| Filename | What to capture |
|---|---|
| `banner.png` | Full app window, used at the top of the README |
| `main-window-overview.png` | Full window with a video loaded (Temporal Timeline visible) |
| `left-sidebar-frame-tab.png` | Left sidebar, "Frame Annotations" tab active |
| `left-sidebar-video-tab.png` | Left sidebar, "Video Annotations" tab, mid-tag ("Mark End" showing) |
| `right-sidebar.png` | Full right sidebar: Object Detection rows, Game State row, Annotation Status table, Quick Annotate button |
| `game-state-range-dialog.png` | The "Classify Game State" dialog, captured right after clicking **Range…** on the Game State row |
| `temporal-timeline.png` | Temporal Timeline with segments across all three rows, one mid-drag if possible |
| `annotation-stats-dialog.png` | Statistics dialog, bar chart view |
| `yolo-export-dialog.png` | YOLO export dialog with options filled in |
| `videomae-export-dialog.png` | VideoMAE export dialog with options filled in |
