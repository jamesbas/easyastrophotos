# Astro.md — System Requirements for an Easy Astrophotography Stacking & Processing App

## 1. Product Vision

Build an easy-to-use astrophotography image processing application that lets a hobbyist import raw astro image frames, stack them, compare original vs processed previews, and apply advanced post-processing techniques through a simple guided UI.

The app should mimic the most useful capabilities of tools such as PixInsight, Siril, and GraXpert, but with a simpler user experience focused on fast workflows, clear before/after previews, and beginner-friendly controls.

The application should support a phased build approach so it can be vibe-coded in Visual Studio Code incrementally.

---

## 2. Research Summary: Capabilities to Mimic

### 2.1 PixInsight-Inspired Capabilities

PixInsight is an advanced astrophotography and technical imaging platform. The app should not attempt to clone PixInsight’s full professional depth in Phase 1, but should mimic the simplified user-facing workflow:

- Load light frames and optional calibration frames.
- Calibrate images using darks, flats, and bias/flat-dark frames.
- Register/align images.
- Integrate/stack images into a master image.
- Perform linear-stage processing before stretching.
- Apply photometric or catalog-aware color calibration where possible.
- Apply stretching to reveal faint nebula/galaxy detail.
- Apply noise reduction, sharpening/deconvolution, background extraction, star-aware processing, and final color/contrast adjustments.

Key PixInsight-style workflow concepts to incorporate:

1. **Weighted batch preprocessing style flow**
   - One guided workflow that handles calibration, registration, frame weighting, and integration.
   - Beginner mode should hide complexity.
   - Advanced mode should expose stacking methods, rejection algorithms, and weighting options.

2. **Linear image awareness**
   - The stacked image starts in a dark, flat, linear state.
   - Denoising, background extraction, color calibration, and deconvolution should preferably occur before final stretching.

3. **Process history and non-destructive edits**
   - Every processing step should be saved as a reversible operation.
   - Users should be able to toggle steps on/off and compare results.

4. **Preview-first processing**
   - Every major operation should show before/after results before the user commits.

---

### 2.2 GraXpert-Inspired Capabilities

GraXpert focuses on fast and easy removal of gradients from astro images. It supports background extraction and has AI-based workflows that reduce the need for manual background point selection.

Features to mimic:

- AI-style background extraction / gradient removal.
- Traditional background model options such as RBF, spline, or polynomial-style modeling.
- One-click background correction.
- Correction type options:
  - Subtraction
  - Division
- Smoothing control for the generated background model.
- Denoising strength slider.
- Optional deconvolution / sharpening workflow.
- GPU acceleration where available, with CPU fallback.
- Model manager concept for optional AI models.

The app should make these controls approachable:

- “Remove Light Pollution / Gradient” button.
- “Denoise” slider from 0–100%.
- “Sharpen Nebula / Galaxy Detail” slider.
- Optional “Save Background Model” debug/advanced option.

---

### 2.3 Siril-Inspired Capabilities

Siril provides a strong free/open-source workflow for preprocessing and processing astro images. It supports scripts, calibration, alignment, stacking, photometric color calibration, RGB composition, pixel math, and command-line/headless workflows.

Features to mimic:

- Folder-based image organization:
  - lights
  - darks
  - flats
  - biases
- Convert supported camera/image formats into a processing-friendly internal format.
- Calibrate frames.
- Remove gradients before or after stacking.
- Align/register images.
- Stack images.
- Photometric color calibration against star catalogs when plate solving is available.
- RGB/LRGB/narrowband channel composition.
- Pixel-math-inspired color mapping.
- Scriptable/headless pipeline execution for repeatable workflows.

Important color calibration rule:

- Photometric color calibration must be performed on a linear image before histogram stretching.

---

## 3. Target Users

### 3.1 Primary User

A hobbyist astrophotographer who has captured many light frames and wants a simple tool to stack and enhance them without learning a complex professional application first.

### 3.2 Secondary User

An advanced hobbyist who wants more control over:

- Calibration frame usage
- Stacking algorithms
- Rejection methods
- Stretching curves
- Denoising strength
- Narrowband color mapping
- Export formats

---

## 4. Core User Experience Goals

1. **Simple first-run experience**
   - User opens the app.
   - Adds image folders or drags images into upload zones.
   - Clicks “Stack Images.”
   - Sees original/reference frame and stacked result side-by-side.
   - Applies processing presets with preview.

2. **Before/after preview everywhere**
   - UI must always show:
     - Original/reference frame
     - Current processed preview
   - Include a slider comparison view if possible.

3. **Guided workflow**
   - Steps should be shown in a left-side workflow rail:
     1. Import
     2. Calibrate
     3. Align
     4. Stack
     5. Background Cleanup
     6. Denoise
     7. Stretch
     8. Colorize
     9. Final Adjustments
     10. Export

4. **Beginner and Advanced Modes**
   - Beginner mode: presets and simple sliders.
   - Advanced mode: detailed algorithm options.

5. **Non-destructive pipeline**
   - All operations should be stored as a processing recipe.
   - The app should allow reprocessing from the original stack without degrading quality.

---

## 5. Proposed Technology Stack

### 5.1 Preferred Local/Desktop-Oriented Architecture

Recommended for vibe coding:

- **Frontend:** React + Vite + TypeScript
- **Desktop wrapper:** Tauri or Electron
- **Backend processing service:** Python FastAPI
- **Image processing:** Python scientific stack
  - numpy
  - scipy
  - scikit-image
  - opencv-python
  - astropy
  - photutils
  - astroalign
  - rawpy for DSLR RAW support
  - tifffile / imageio
  - onnxruntime for optional AI models
- **Job queue:** Local background job manager using Python multiprocessing or Celery-lite style queue
- **Storage:** Local project folder with metadata JSON/SQLite
- **Database:** SQLite for project metadata and processing history

### 5.2 Alternate Web Architecture

For web-hosted version:

- **Frontend:** React + Vite + TypeScript
- **Backend:** FastAPI
- **Worker:** Python background worker
- **Storage:** Azure Blob Storage or local file storage
- **Database:** SQLite for local, PostgreSQL for cloud
- **Containerization:** Single Docker container for small personal app; split worker/frontend/backend later if needed

---

## 6. High-Level System Architecture

```text
+--------------------------------------------------+
| React / Vite UI                                  |
| - Project dashboard                              |
| - Import wizard                                  |
| - Processing workflow rail                       |
| - Original vs preview image viewer               |
| - Sliders, presets, export controls              |
+-------------------------+------------------------+
                          |
                          | HTTP / local IPC
                          v
+--------------------------------------------------+
| FastAPI Processing API                           |
| - Project management                             |
| - File upload/indexing                           |
| - Processing job orchestration                   |
| - Preview generation                             |
| - Recipe/history management                      |
+-------------------------+------------------------+
                          |
                          v
+--------------------------------------------------+
| Python Processing Engine                         |
| - Calibration                                    |
| - Alignment / registration                       |
| - Stacking / integration                         |
| - Background extraction                          |
| - Denoising                                      |
| - Stretching                                     |
| - Color mapping                                  |
| - Export                                         |
+-------------------------+------------------------+
                          |
                          v
+--------------------------------------------------+
| Local Project Storage                            |
| - Original frames                                |
| - Calibration frames                             |
| - Intermediate FITS/TIFF files                   |
| - Preview PNG/JPEG files                         |
| - SQLite metadata                                |
| - Processing recipe JSON                         |
+--------------------------------------------------+
```

---

## 7. Functional Requirements

## 7.1 Project Management

### Requirements

- User can create a new astro processing project.
- User can name the project.
- User can select a target type:
  - Galaxy
  - Nebula
  - Star cluster
  - Moon / planetary
  - Milky Way / landscape astro
  - Unknown / auto-detect
- User can save and reopen projects.
- App stores all settings in a project recipe file.

### Acceptance Criteria

- A project can be created and reopened.
- Processing history is preserved.
- The app can regenerate previews from saved recipe steps.

---

## 7.2 Image Import

### Supported Input Types

Phase 1:

- FITS
- TIFF
- PNG
- JPEG

Phase 2:

- DSLR RAW formats via rawpy:
  - CR2
  - CR3
  - NEF
  - ARW
  - DNG

Phase 3:

- SER video files
- FITS sequences
- Multi-channel monochrome datasets

### Import Categories

User should be able to import:

- Light frames
- Dark frames
- Flat frames
- Bias frames
- Flat dark frames

### UI Requirements

Create drag-and-drop zones:

- “Drop Light Frames Here”
- “Optional: Drop Darks”
- “Optional: Drop Flats”
- “Optional: Drop Bias / Flat Darks”

Show a frame count and thumbnail strip for each category.

### Acceptance Criteria

- User can import at least 20 light frames.
- UI shows imported frame counts.
- User can remove bad frames before stacking.
- App warns if no light frames are imported.

---

## 7.3 Calibration

### Purpose

Remove sensor noise, dark current, dust shadows, vignetting, and optical defects using calibration frames.

### Requirements

- Create master dark, master flat, master bias, and/or master flat dark.
- Calibrate each light frame using available calibration frames.
- If calibration frames are missing, allow stacking lights only with warning.
- Implement beginner-friendly language:
  - “Darks remove sensor heat noise.”
  - “Flats remove dust spots and vignetting.”
  - “Bias/flat darks remove camera readout signal.”

### Basic Calibration Formula

```text
calibrated_light = (light - master_dark - master_bias) / normalized_master_flat
```

If using unprocessed darks that already include bias signal:

```text
calibrated_light = (light - master_dark) / normalized_master_flat
```

### Advanced Options

- Dark optimization on/off
- Flat normalization method
- Cosmetic correction for hot/cold pixels
- Bad pixel map support

### Acceptance Criteria

- App can create master calibration frames.
- App can calibrate all light frames.
- App displays a preview of one calibrated frame vs original frame.

---

## 7.4 Frame Quality Analysis

### Requirements

Analyze each light frame for:

- Star count
- Star sharpness / FWHM approximation
- Background brightness
- Noise estimate
- Cloud/haze indicator
- Frame score

### UI Requirements

- Show a sortable frame table.
- Allow the user to exclude poor frames.
- Provide an “Auto-select best frames” button.

### Frame Scoring

Create a composite score using:

```text
score = weighted_star_count + weighted_sharpness - weighted_noise - weighted_background_gradient
```

### Acceptance Criteria

- Frames receive quality scores.
- User can exclude frames manually.
- Auto-select can keep the top N% of frames.

---

## 7.5 Registration / Alignment

### Requirements

- Select best frame as reference automatically.
- Align all frames to the reference frame.
- Use star detection and geometric transform matching.
- Use astroalign or equivalent triangle/asterism matching.
- Support translation, rotation, and scale correction.

### Advanced Options

- Manual reference frame selection
- Star detection threshold
- Maximum control points
- Transformation type:
  - Translation only
  - Similarity
  - Affine
  - Projective

### Acceptance Criteria

- Frames with slight drift and rotation align successfully.
- UI displays before/after alignment preview.
- Failed alignments are reported and skipped unless user overrides.

---

## 7.6 Stacking / Integration

### Requirements

Implement stacking into a master image.

### Beginner Options

- Standard Stack
- Best Quality Stack
- Fast Preview Stack

### Advanced Integration Methods

- Average
- Median
- Weighted average
- Sigma clipping
- Winsorized sigma clipping
- Min/max rejection

### Weighting Options

- Equal weight
- Quality score weight
- FWHM/sharpness weight
- Noise weight

### Output

- Master stacked image in high bit-depth format.
- Preview PNG/JPEG for UI rendering.
- Metadata summary:
  - Number of frames stacked
  - Total integration time if exposure metadata is available
  - Rejected frame count
  - Stacking method

### Acceptance Criteria

- App can stack 10+ aligned frames into one image.
- App saves the master stack.
- UI displays original/reference frame vs stacked preview.

---

## 7.7 Background Extraction / Gradient Removal

### Purpose

Remove light pollution gradients, vignetting leftovers, moonlight gradients, and color casts.

### Requirements

Beginner mode:

- One button: “Remove Light Pollution / Gradient”
- Slider: “Strength”
- Toggle: “Protect Nebula / Galaxy”

Advanced mode:

- Background model type:
  - Polynomial surface
  - Radial basis function
  - Spline-like interpolation
  - AI model placeholder
- Correction type:
  - Subtraction
  - Division
- Smoothing slider
- Sample point editor for manual background points
- Save background model option

### Acceptance Criteria

- App can estimate and remove a smooth gradient.
- App can show background model preview.
- User can compare before/after gradient removal.

---

## 7.8 Denoising

### Requirements

Beginner mode:

- Slider: “Denoise Strength”
- Presets:
  - Light
  - Balanced
  - Strong

Advanced mode:

- Algorithm choices:
  - Non-local means
  - Wavelet denoise
  - Bilateral filter
  - AI/ONNX model placeholder
- Protect stars toggle
- Protect fine detail toggle
- Mask preview

### Processing Guidance

- Prefer denoising while the image is still linear, before aggressive stretching.
- Allow post-stretch denoising as a final cleanup pass.

### Acceptance Criteria

- App reduces visible noise without destroying star fields.
- Preview updates after parameter changes.
- User can apply or cancel denoise operation.

---

## 7.9 Deconvolution / Sharpening

### Requirements

Beginner mode:

- Slider: “Sharpen Details”
- Presets:
  - Gentle
  - Nebula Detail
  - Galaxy Detail
  - Star Tightening

Advanced mode:

- Deconvolution method:
  - Richardson-Lucy
  - Wiener
  - AI/ONNX model placeholder
- Separate modes:
  - Object detail enhancement
  - Stellar deconvolution / star tightening
- Strength parameter
- FWHM estimate parameter
- Ringing artifact protection

### Acceptance Criteria

- App can sharpen galaxy/nebula structures.
- App can reduce bloated star appearance without harsh artifacts.
- User can preview before applying.

---

## 7.10 Stretching

### Purpose

Transform the dark linear stacked image into a visible non-linear image.

### Beginner Mode

Presets:

- Auto Stretch
- Gentle Nebula Stretch
- Galaxy Core Protection
- Star Cluster Natural Stretch
- Milky Way Widefield Stretch

### Advanced Mode

Controls:

- Black point
- Midtones
- White point
- Shadows clipping protection
- Highlight/core protection
- Curves adjustment
- Generalized hyperbolic stretch-inspired option
- Arcsinh stretch option
- Histogram transform option

### Acceptance Criteria

- Linear stacked image becomes visible after stretch.
- Stars are not clipped by default.
- Galaxy cores are protected when using galaxy preset.
- User can reset stretch settings.

---

## 7.11 Color Calibration and Colorization

### Requirements

Support three main color workflows:

1. **Natural RGB color calibration**
   - For one-shot color or RGB datasets.
   - White balance adjustment.
   - Background neutralization.
   - Optional photometric color calibration if plate solving is available.

2. **Hubble-style narrowband palette mapping**
   - For monochrome narrowband stacks.
   - Default Hubble/SHO mapping:
     - SII → Red
     - H-alpha → Green
     - OIII → Blue
   - Include note in UI that Hubble/SHO is scientifically inspired false color, not true natural color.

3. **Naturalized Hubble color option**
   - Start from SHO mapping.
   - Reduce excessive green cast.
   - Balance star colors if RGB stars are available.
   - Offer “Hubble Natural,” “Classic Hubble,” and “Soft Hubble” presets.

### UI Requirements

Color panel should include:

- Color mode:
  - Natural RGB
  - Hubble SHO
  - HOO
  - Custom channel mapping
- Channel assignment dropdowns:
  - Red channel source
  - Green channel source
  - Blue channel source
- Saturation slider
- Green reduction slider
- Star color preservation toggle
- Background neutralization toggle

### Acceptance Criteria

- User can apply natural RGB color balance to OSC/RGB data.
- User can apply SHO palette to narrowband data.
- User can preview color mapping changes immediately.

---

## 7.12 Star Processing

### Phase 2+ Requirements

- Detect stars.
- Generate star mask.
- Optional star reduction.
- Optional star color boost.
- Optional starless preview.
- Separate star and object processing pipeline if feasible.

### Acceptance Criteria

- App can generate a visible star mask.
- App can reduce star intensity without damaging nebula/galaxy detail.

---

## 7.13 Preview and Comparison Viewer

### Requirements

The UI must show:

- Original/reference frame
- Current processed result
- Optional stacked linear preview
- Optional final export preview

Viewer controls:

- Side-by-side view
- Split slider view
- Zoom and pan
- Fit to screen
- 100% pixel view
- Histogram panel
- Pixel value inspector
- Toggle overlays:
  - Star mask
  - Rejected pixels
  - Background model

### Acceptance Criteria

- User can visually compare original and processed image.
- User can zoom/pan both views in sync.
- User can switch between before/after and slider comparison.

---

## 7.14 Presets

### Built-In Beginner Presets

- Quick Stack + Auto Enhance
- Nebula Enhancement
- Galaxy Detail
- Star Cluster Natural
- Light Pollution Cleanup
- Hubble Color Nebula
- Soft Natural Color

### Preset Definition Format

Store presets as JSON:

```json
{
  "name": "Nebula Enhancement",
  "description": "Balanced stretch, gradient removal, denoise, and moderate saturation for emission nebulae.",
  "steps": [
    { "operation": "background_extraction", "strength": 0.65, "smoothing": 0.70, "correction": "subtraction" },
    { "operation": "denoise", "strength": 0.45, "protect_stars": true },
    { "operation": "stretch", "method": "arcsinh", "black_point": 0.02, "midtone": 0.42 },
    { "operation": "color", "mode": "natural_rgb", "saturation": 0.25 }
  ]
}
```

### Acceptance Criteria

- User can apply a preset.
- User can customize a preset and save it as a new preset.

---

## 8. Non-Functional Requirements

### 8.1 Performance

- Generate thumbnails quickly after import.
- Run long processing jobs asynchronously.
- Show progress bars and job logs.
- Avoid blocking the UI during stacking or denoising.
- Use chunked/tiled processing for large images.

### 8.2 Reliability

- App must not overwrite original image files.
- Intermediate files should be recoverable.
- Failed jobs should provide readable error messages.
- Processing should be restartable from the last completed stage.

### 8.3 Usability

- Beginner mode must use plain English labels.
- Advanced terms should include tooltip explanations.
- App should explain why calibration frames matter.
- App should warn users before destructive export compression.

### 8.4 Privacy

- Local-first processing by default.
- No image upload to cloud unless the user explicitly enables cloud mode.
- Project data remains in the selected local project folder.

### 8.5 Hardware

- CPU-only support required.
- GPU acceleration optional.
- If GPU is available, support ONNX Runtime acceleration where possible.
- App should detect available memory and warn before large stacks.

---

## 9. Data Model

### 9.1 Project Metadata

```json
{
  "project_id": "uuid",
  "name": "Orion Nebula Session",
  "created_at": "2026-05-09T20:00:00Z",
  "target_type": "nebula",
  "project_path": "/projects/orion-nebula",
  "status": "active"
}
```

### 9.2 Frame Metadata

```json
{
  "frame_id": "uuid",
  "project_id": "uuid",
  "file_path": "/projects/orion/lights/light_001.fit",
  "frame_type": "light",
  "width": 6248,
  "height": 4176,
  "bit_depth": 16,
  "exposure_seconds": 120,
  "iso_or_gain": 800,
  "temperature_c": -10,
  "filter": "Ha",
  "quality_score": 0.87,
  "included": true
}
```

### 9.3 Processing Recipe

```json
{
  "project_id": "uuid",
  "current_step": "colorize",
  "steps": [
    {
      "id": "step-001",
      "operation": "calibration",
      "params": {
        "use_darks": true,
        "use_flats": true,
        "use_bias": true
      },
      "output_file": "calibrated_sequence.seq"
    },
    {
      "id": "step-002",
      "operation": "stacking",
      "params": {
        "method": "weighted_average",
        "rejection": "sigma_clip"
      },
      "output_file": "master_stack.fit"
    }
  ]
}
```

---

## 10. API Requirements

### 10.1 Project APIs

```text
POST /api/projects
GET /api/projects
GET /api/projects/{project_id}
DELETE /api/projects/{project_id}
```

### 10.2 Import APIs

```text
POST /api/projects/{project_id}/frames
GET /api/projects/{project_id}/frames
DELETE /api/projects/{project_id}/frames/{frame_id}
PATCH /api/projects/{project_id}/frames/{frame_id}
```

### 10.3 Processing APIs

```text
POST /api/projects/{project_id}/jobs/calibrate
POST /api/projects/{project_id}/jobs/analyze-frames
POST /api/projects/{project_id}/jobs/register
POST /api/projects/{project_id}/jobs/stack
POST /api/projects/{project_id}/jobs/background-extraction
POST /api/projects/{project_id}/jobs/denoise
POST /api/projects/{project_id}/jobs/deconvolution
POST /api/projects/{project_id}/jobs/stretch
POST /api/projects/{project_id}/jobs/colorize
POST /api/projects/{project_id}/jobs/export
```

### 10.4 Job APIs

```text
GET /api/jobs/{job_id}
GET /api/jobs/{job_id}/logs
POST /api/jobs/{job_id}/cancel
```

### 10.5 Preview APIs

```text
GET /api/projects/{project_id}/preview/original
GET /api/projects/{project_id}/preview/current
GET /api/projects/{project_id}/preview/step/{step_id}
GET /api/projects/{project_id}/histogram/current
```

---

## 11. UI Requirements

## 11.1 Main Layout

Use a clean three-pane layout:

```text
+--------------------------------------------------------------+
| Top Bar: Project Name | Save | Undo | Redo | Export          |
+----------------+-------------------------------+-------------+
| Workflow Rail  | Image Viewer                   | Controls    |
|                | Original | Preview             |             |
| 1 Import       |                               | Step params |
| 2 Calibrate    |                               | Presets     |
| 3 Align        |                               | Apply       |
| 4 Stack        |                               | Reset       |
| 5 Cleanup      |                               |             |
| 6 Denoise      |                               |             |
| 7 Stretch      |                               |             |
| 8 Colorize     |                               |             |
| 9 Export       |                               |             |
+----------------+-------------------------------+-------------+
```

## 11.2 Import Screen

- Drag-and-drop zones for each frame type.
- File browser button.
- Thumbnail list.
- Frame count.
- Validation warnings.
- “Start Analysis” button.

## 11.3 Processing Screen

- Left workflow rail with completed/current/pending status.
- Center image viewer with side-by-side original and preview.
- Right controls panel with beginner sliders and advanced accordion.

## 11.4 Export Screen

Export options:

- 16-bit TIFF
- PNG
- JPEG
- FITS
- Processing recipe JSON
- Before/after comparison image

---

## 12. Phased Implementation Plan

## Phase 1 — Minimum Viable Astro Stacker

Goal: Build a working local app that imports images, aligns, stacks, stretches, and shows original vs preview.

### Phase 1 Features

- React/Vite UI shell.
- FastAPI backend.
- Create/open project.
- Import light frames.
- Thumbnail generation.
- Basic frame analysis.
- Basic alignment using astroalign/OpenCV.
- Stack using average or median.
- Auto stretch.
- Original vs stacked preview.
- Export PNG/TIFF.

### Phase 1 Acceptance Criteria

- User can import at least 10 light frames.
- User can stack them.
- User can see original/reference image and stacked result side-by-side.
- User can apply auto stretch.
- User can export the processed image.

---

## Phase 2 — Calibration and Better Stacking

Goal: Add real astrophotography preprocessing.

### Phase 2 Features

- Add dark, flat, bias import.
- Create master calibration frames.
- Calibrate light frames.
- Add weighted average stacking.
- Add sigma clipping.
- Add frame exclusion table.
- Add project recipe/history.

### Phase 2 Acceptance Criteria

- User can calibrate frames using darks/flats/biases.
- User can reject bad frames.
- User can use sigma clipping.
- Processing recipe is saved and reloadable.

---

## Phase 3 — Background Extraction, Denoising, and Advanced Stretching

Goal: Add GraXpert-like and PixInsight-like post-processing basics.

### Phase 3 Features

- Gradient/background extraction.
- Background model preview.
- Denoising sliders.
- Deconvolution/sharpening slider.
- Histogram stretch.
- Arcsinh stretch.
- Curves adjustment.
- Before/after split slider.

### Phase 3 Acceptance Criteria

- User can remove a light pollution gradient.
- User can denoise without destroying stars.
- User can apply multiple stretch methods.
- User can compare before/after for each operation.

---

## Phase 4 — Color Calibration and Hubble/Narrowband Palette

Goal: Add color workflows for RGB, OSC, and narrowband data.

### Phase 4 Features

- Background neutralization.
- RGB color balance.
- Photometric color calibration placeholder.
- Plate solving integration placeholder.
- Hubble SHO mapping.
- HOO mapping.
- Custom channel mapping.
- Green reduction.
- Saturation controls.

### Phase 4 Acceptance Criteria

- User can apply natural RGB color adjustments.
- User can map SII/Ha/OIII to RGB using Hubble SHO palette.
- UI clearly explains true color vs false color.

---

## Phase 5 — AI-Assisted Enhancements

Goal: Add optional model-based image enhancement.

### Phase 5 Features

- ONNX Runtime integration.
- AI denoise model placeholder.
- AI background extraction model placeholder.
- AI deconvolution model placeholder.
- GPU/CPU toggle.
- Model manager screen.

### Phase 5 Acceptance Criteria

- App can detect GPU availability.
- App can run ONNX inference if a compatible model is installed.
- App can fall back to CPU.

---

## Phase 6 — Advanced User Features

Goal: Add power-user capabilities without compromising the beginner UI.

### Phase 6 Features

- Star mask generation.
- Star reduction.
- Starless processing placeholder.
- Pixel math panel.
- Scriptable workflow export/import.
- Batch project processing.
- Headless CLI mode.
- Cloud/container deployment option.

### Phase 6 Acceptance Criteria

- User can save a repeatable processing workflow.
- User can run a saved recipe on another dataset.
- Advanced controls remain hidden unless enabled.

---

## 13. Suggested Folder Structure

```text
astro-app/
  frontend/
    src/
      components/
        ImageViewer/
        WorkflowRail/
        ImportPanel/
        ControlsPanel/
        HistogramPanel/
        ExportPanel/
      pages/
      services/
      types/
      App.tsx
      main.tsx
  backend/
    app/
      main.py
      api/
      models/
      services/
        project_service.py
        frame_service.py
        job_service.py
      processing/
        calibration.py
        frame_analysis.py
        registration.py
        stacking.py
        background.py
        denoise.py
        deconvolution.py
        stretch.py
        color.py
        export.py
      storage/
      workers/
    requirements.txt
  shared/
    schemas/
  docs/
    Astro.md
  docker/
  README.md
```

---

## 14. Development Instructions for Vibe Coding

When using this file in VS Code with an AI coding assistant, instruct it to work phase-by-phase.

### Recommended Prompt

```text
Use Astro.md as the master system requirements document. Build this app phase by phase. Start with Phase 1 only. Do not implement later phases until Phase 1 is working and tested. Create a React + Vite + TypeScript frontend and a Python FastAPI backend. Implement project creation, light-frame import, thumbnail generation, basic registration/alignment, simple stacking, auto stretch, original-vs-preview display, and export. Keep the UI simple and beginner-friendly. Use modular code so later phases can add calibration, denoising, background extraction, and colorization.
```

---

## 15. Testing Requirements

### Unit Tests

- Image loading
- Thumbnail generation
- Calibration frame creation
- Alignment transform calculation
- Stacking algorithms
- Stretch functions
- Color mapping functions

### Integration Tests

- Import → stack → stretch → export
- Import with bad frame exclusion
- Project save/reopen
- Processing recipe replay

### Test Data

Include a small test dataset:

```text
/test-data/
  m42-small/
    lights/
    darks/
    flats/
    biases/
```

If real astro test data is not available, generate synthetic star fields for automated testing.

---

## 16. Important UX Warnings and Educational Copy

The app should include small helper notes:

- “Your stacked image may look very dark at first. This is normal. It is still linear and contains hidden faint detail.”
- “Denoising is usually best before stretching because stretching makes noise more visible.”
- “Hubble Palette is false color. It maps sulfur, hydrogen, and oxygen emissions into visible RGB channels to reveal structure.”
- “Photometric color calibration should be done before stretching.”
- “Original files are never modified.”

---

## 17. Source-Informed Design Notes

- PixInsight is positioned as an advanced image processing platform designed for astrophotography and technical imaging.
- PixInsight-style workflows commonly include calibration, registration, integration/stacking, linear-stage processing, denoising, sharpening/deconvolution, stretching, star processing, and color/contrast refinement.
- GraXpert is focused on removing gradients from astroimages and supports AI-style background extraction, denoising, and deconvolution-style operations through simple parameters such as smoothing, correction type, strength, FWHM, and GPU/CPU options.
- Siril’s workflow emphasizes calibration, conversion to FITS, alignment, stacking, photometric color calibration, RGB composition, pixel math, scripting, and headless automation.
- Siril documentation warns that photometric color calibration should be performed on a linear image before histogram stretching.
- Hubble/SHO palette should be treated as scientifically inspired false color: SII → Red, H-alpha → Green, OIII → Blue. The app should also offer “naturalized” variants that reduce excessive green cast and create a more visually pleasing result.

---

## 18. Out of Scope for Initial Build

Do not implement in Phase 1:

- Full PixInsight-equivalent process library
- Full plate solving
- Full photometric color calibration
- Full AI model training
- Cloud multi-user accounts
- Telescope/camera acquisition control
- Planetary lucky imaging pipeline
- Real-time live stacking

These can be added later after the base processing workflow is stable.

---

## 19. Definition of Done for MVP

The MVP is complete when:

1. User can create a project.
2. User can import light frames.
3. User can align/register images.
4. User can stack images.
5. User can auto-stretch the stacked image.
6. User can see original/reference image and processed preview side-by-side.
7. User can export a final PNG or TIFF.
8. User can reopen the project and see the prior result.
9. The codebase is modular enough to add calibration, denoising, background extraction, stretching, and colorization in later phases.
