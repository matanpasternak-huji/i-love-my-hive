# PyQt GUI Design — Bee Interaction Detector

**Date:** 2026-05-01  
**Status:** Approved

---

## Overview

A PyQt5 desktop application that wraps the existing pipeline scripts into a GUI. The app has two entry points from a home screen: running the full pipeline on a video, or permanently replacing the active SLEAP model.

---

## Architecture

The GUI is a single-window `QMainWindow` with a `QStackedWidget` managing four pages:

| Index | Page | Class |
|-------|------|-------|
| 0 | Home | `HomePage` |
| 1 | Run Pipeline — idle | `PipelinePage` |
| 2 | Run Pipeline — running | `RunningPage` |
| 3 | Update Model | `UpdateModelPage` |

Navigation:
- Home → Pipeline: "Run Pipeline" button
- Home → Update Model: "Update Model" button
- Pipeline → Home: back arrow (top-left)
- Update Model → Home: "← Back to home" link
- Pipeline idle → Running: "Run Pipeline" button (validates inputs first)
- Running → Home: pipeline completes or user cancels

A single `AppState` object (plain Python dataclass) holds:
- `model_path: str` — path to the active model folder (persisted in `config.json`)
- `model_name: str` — display name (folder basename)

`config.json` lives next to `main.py` and is read on startup / written on model replace.

---

## Page 1 — Home

**Layout:** Dark background (`#0d1117`), centred column, full window size.

**Bee animation:**  
Seven `🐝` emoji `QLabel`s positioned absolutely over the window using `setGeometry`. Each bee's position is driven by a `QTimer` (16 ms tick) that evaluates a fixed sinusoidal path (unique amplitude, frequency, and phase per bee) and calls `move()`. No rotation — the emoji reads as a bee from any direction. Duration equivalent: 7–13 s per cycle, staggered so bees stay spread across the window.

**Widgets (z-ordered above bees):**
- Title label: `🐝 Bee Interaction Detector` (bold, 22 pt)
- Subtitle label: `SLEAP · NAPS · Antennation` (muted, 10 pt)
- **Run Pipeline** button (green, 220 px wide)
- **Update Model** button (dark, 220 px wide)
- Active model label: `Active model: <name>` (small, muted, bottom of column)

---

## Page 2 — Run Pipeline (idle)

**Widgets top to bottom:**

### Video File
Drop-zone widget (`QFrame` with `dragEnterEvent` / `dropEvent`) accepting `.mp4` files. Also has a **Browse…** button that opens `QFileDialog`. Displays the chosen filename once selected.

### Active Model
Read-only badge showing the current model name with a green dot. No upload affordance here.

### Parameters
2 × 2 grid of parameter cells. Each cell contains:
- Label (parameter name)
- `QSpinBox` or `QDoubleSpinBox` for the value
- Unit text below the spinbox (small, muted)
- **?** button (red circle, 18 px) — clicking opens a `QToolTip`-style `QDialog` anchored near the button

| Parameter | Widget | Default | Unit label |
|-----------|--------|---------|------------|
| Exit Radius | `QDoubleSpinBox` (0.1–10, step 0.1) | 1.0 | × avg body length |
| Cancel Time | `QSpinBox` (1–9999) | 1500 | frames |
| Touch Frames | `QSpinBox` (1–100) | 1 | frames to enter |
| Touch Distance | `QSpinBox` (1–500) | 50 | pixels |

**Tooltip popup content (? button):**

| Parameter | Explanation |
|-----------|-------------|
| Exit Radius | How far a bee's head must move from the interaction centre (measured as a multiple of the average bee body length) before the interaction ends. |
| Cancel Time | Maximum interaction duration in frames. Interactions still active after this many frames are marked "canceled". |
| Touch Frames | How many consecutive frames both bees must have their antenna tips within Touch Distance before an interaction is counted as started. |
| Touch Distance | Maximum pixel distance between antenna tips to be considered "touching". |

### Visualization
Two `QCheckBox`es:
- Save annotated video (default: checked)
- Show video when done (default: checked)

### Run Button
Green **▶ RUN PIPELINE** button. Disabled until a video file is selected. Clicking validates inputs then switches to the Running page and starts the pipeline subprocess.

---

## Page 3 — Run Pipeline (running)

A separate stack page (index 2). Inputs from the idle page are passed in when switching.

**Widgets:**

### Collapsed input summary
Single `QLabel` block showing the chosen video, model name, and parameter snapshot. Muted color. Not interactive.

### Progress bar
`QProgressBar` + step label (`QLabel`) above it.  
Step parsing: pipeline stdout is scanned for the pattern `Step N/3 —` to set the bar to `(N-1)/3 * 100` at step start and `N/3 * 100` at `[OK]`.

### Log output
`QPlainTextEdit` (read-only, monospace font, dark background) that receives live stdout from the subprocess. Lines are color-coded:
- `[OK]` lines → green
- `[ERROR]` lines → red
- default → muted white

### Cancel button
Dark red **■ CANCEL** button. Sends `SIGTERM` to the subprocess and navigates back to the idle pipeline page with inputs preserved.

### On completion
When the subprocess exits with code 0: show a brief `QMessageBox` ("Pipeline complete — outputs saved to `<dir>`"), then return to Home. If `Show video when done` was checked and the output video exists, open it with the system default player (`QDesktopServices.openUrl`).

---

## Page 4 — Update Model

**Widgets:**

- **← Back to home** link label (top-left)
- **Current Model** read-only box showing active model name
- Drop-zone `QFrame` accepting a folder drop (or **Browse…** for folder via `QFileDialog.getExistingDirectory`). Validates that the dropped folder contains at least one `.pb` or `.h5` file.
- Warning box: `⚠ Permanently replaces the active model. Previous model will be removed.`
- **🧠 REPLACE MODEL** button — disabled until a valid model folder is staged
- Small note: `(activates once a model is dropped)`

**On confirm:**
1. Delete the existing model folder at `model_path`
2. Copy the new folder into the same parent directory
3. Update `config.json` with the new path and name
4. Update `AppState`
5. Show `QMessageBox` confirmation
6. Navigate back to Home (active model label updates automatically)

---

## Pipeline subprocess integration

`main.py` already orchestrates the three steps. The GUI calls:

```python
self.process = QProcess(self)
self.process.readyReadStandardOutput.connect(self._on_stdout)
self.process.finished.connect(self._on_finished)
self.process.start(sys.executable, [
    "main.py",
    "--input", video_path,
    "--output", output_dir,
])
```

Parameters are passed as CLI flags. `find_interactions_by_antennation.py` must be updated to accept `--touch-thresh`, `--min-touch-frames`, `--d-exit-factor`, and `--max-frames` arguments, which the GUI populates from the spinboxes before launching the subprocess.

The output directory is a timestamped subfolder inside `output/` (matches existing `main.py` behaviour).

---

## Config persistence

`config.json` (next to `main.py`):

```json
{
  "model_path": "Current Model/260317_163723.multi_instance.n=240",
  "model_name": "260317_163723.multi_instance"
}
```

Read on app startup. Written only on model replace.

---

## Files to create / modify

| Action | File |
|--------|------|
| **Create** | `gui.py` — main entry point, `QApplication` + `MainWindow` |
| **Create** | `gui_pages/home.py` |
| **Create** | `gui_pages/pipeline_idle.py` |
| **Create** | `gui_pages/pipeline_running.py` |
| **Create** | `gui_pages/update_model.py` |
| **Create** | `gui_pages/__init__.py` |
| **Create** | `config.json` (initial, points at existing model) |
| **Modify** | `find_interactions_by_antennation.py` — add CLI flags for all 4 parameters |

---

## Dependencies

- `PyQt5` (or `PyQt6` — prefer PyQt5 for broadest conda/pip compatibility)
- All existing deps already present

---

## Out of scope

- User accounts / multi-user
- Remote execution
- Results viewer / analysis within the GUI (outputs are files on disk)
- Dark/light theme toggle
