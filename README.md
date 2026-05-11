# Easy Astro Photos

An easy-to-use astrophotography image stacking and processing application.
Implements **Phases 1–6** of the design in
[Astro App Design Requirements.md](Astro%20App%20Design%20Requirements.md).

- Python FastAPI backend (image processing engine: numpy / scipy / scikit-image
  / OpenCV / astropy / astroalign / PyWavelets, optional ONNX Runtime)
- React + Vite + TypeScript frontend
- Local SQLite metadata, on-disk per-project folders, non-destructive recipe
  pipeline that can be replayed from the master stack at any time
- **Astro-tuned classical pipeline**: starlet (à trous wavelet) denoise,
  PSF-auto-estimated Richardson-Lucy deconvolution with TV regularization,
  and Abe-style background extraction with local-percentile sampling
- Optional **GPU-accelerated AI denoise** via ONNX (CUDA EP on NVIDIA, DirectML
  on any DX12 GPU). Tile-based inference with Hann-window blending handles
  arbitrary frame sizes without VRAM blow-up.

---

## Quick start (Windows / PowerShell)

> [!IMPORTANT]
> The backend listens on **port 8766**. The Vite dev server proxies `/api` →
> `http://localhost:8766`. If you change the backend port, update
> `frontend/vite.config.ts` to match.

### 1. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8766
```

API docs: <http://localhost:8766/docs>

Per-user data (SQLite + project folders) lives under
`%LOCALAPPDATA%\EasyAstroPhotos`. Override with `EAP_DATA_DIR`.

### 2. Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>.

---

## Classical processing pipeline

Every AI feature has a strong classical fallback. These are the defaults you
get out of the box (no model files required):

| Step       | Algorithm                                                                           |
| ---------- | ----------------------------------------------------------------------------------- |
| Background | Abe-style: grid-based local-percentile sampling → iterative sigma-clip rejection → thin-plate-spline RBF surface (`background.py`) |
| Denoise    | **Starlet (à trous wavelet)** with per-scale threshold `(3.5 + 1.5·strength) · 0.5ʲ` and preserved coarse residual; optional star protection mask (`denoise.py`) |
| Sharpen    | **PSF-auto-estimated Richardson-Lucy** with TV regularization. PSF is built from stacked, sub-pixel-recentered, unsaturated star patches; `fwhm=0` in the UI triggers auto-estimate (`deconvolution.py`) |

These produce excellent results on most targets. The AI hooks below are
optional speedups / quality bumps for *post-stretch* frames.

## Phase 5 — AI features (optional)

The denoise / background / sharpen panels each have an "AI" method that runs
an ONNX model. **None of the AI features work until you install ONNX Runtime
*and* drop a model file into the `models/` folder.** Without those, the AI
options silently fall back to the classical implementations above.

### Install ONNX Runtime

Run **inside the activated backend venv** (this only affects this project):

| Hardware                    | Command                                  | Notes                                                                                            |
| --------------------------- | ---------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Any DirectX 12 GPU (Windows)| `pip install onnxruntime-directml`       | **Recommended on Windows.** Works on NVIDIA / AMD / Intel without matching CUDA versions.        |
| NVIDIA + matching CUDA      | `pip install onnxruntime-gpu`            | Needs the exact CUDA + cuDNN combo the wheel was built for. Skip if you don't already have CUDA. |
| CPU-only                    | `pip install onnxruntime`                | Fallback. Slow but reliable.                                                                     |

> [!WARNING]
> Install only **one** of the three. If you need to switch, run
> `pip uninstall onnxruntime onnxruntime-gpu onnxruntime-directml` first.

> [!NOTE]
> The "GPU available: yes/no" indicator in the AI Models panel reports what
> *ONNX Runtime* can target — not whether your machine physically has a GPU.
> If it says "no" but you have a GPU, install the right runtime above.

### Python version note

ONNX Runtime sometimes lags new Python releases. If `pip install` cannot find
a matching wheel for your venv's Python (e.g. Python 3.14), recreate the venv
with Python 3.12:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install onnxruntime-directml
```

### Where models live

The backend looks for `.onnx` files in this order:

1. `EAP_MODELS_DIR` environment variable (if set)
2. `<repo>/models/` (preferred for local development)
3. `%LOCALAPPDATA%\EasyAstroPhotos\models\` (per-user fallback)

Files are auto-assigned to a feature by **filename prefix**:

| Prefix              | Feature                       |
| ------------------- | ----------------------------- |
| `denoise*.onnx`     | AI denoise                    |
| `background*.onnx`  | AI background extraction      |
| `decon*.onnx`       | AI deconvolution / sharpening |

See [`models/README.md`](models/README.md) for the full I/O contract and a
realistic discussion of what models actually exist (spoiler: the production
astrophotography ones are commercial; you can convert SCUNet/DRUNet from
PyTorch yourself).

A helper script lists curated starting points:

```powershell
cd backend
python scripts\download_models.py
```

### Convert SCUNet to ONNX (recommended denoiser)

SCUNet (Zhang et al., Apache 2.0) is a strong general-purpose denoiser. It is
*not* trained on astro data, but on **post-stretch** RGB frames it routinely
beats classical NLM and the starlet filter on noise grain.

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install torch --index-url https://download.pytorch.org/whl/cu130       # NVIDIA RTX 50xx (CUDA 13)
# OR  pip install torch --index-url https://download.pytorch.org/whl/cu121 # other NVIDIA / CUDA 12
# OR  pip install torch                                                    # CPU-only
pip install einops timm thop onnxscript    # SCUNet network deps + dynamo exporter
python scripts\convert_scunet.py
```

This produces [`models/denoise_scunet_color.onnx`](models/denoise_scunet_color.onnx) (~3.7 MB).
Pick the "AI" denoise method in the UI to use it. Variants `--variant color_real_gan`
and `--variant gray_25` are also available.

### Verified RTX 50-series GPU setup (Blackwell, sm_120)

Tested working on an RTX 5070 Ti with Python 3.14 on Windows. Benchmark:
**~11 s** to denoise a 3000 × 4500 RGB frame with SCUNet via 256-px tiled
inference.

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
# 1. Torch with CUDA 13 (only torch needs CUDA 13; ORT still needs CUDA 12 below)
pip install torch==2.11.0 torchvision --index-url https://download.pytorch.org/whl/cu130
# 2. Swap DirectML for the CUDA Execution Provider
pip uninstall -y onnxruntime onnxruntime-directml
pip install onnxruntime-gpu
# 3. ORT 1.26 is linked against CUDA 12 / cuDNN 9 — install the user-space wheels
pip install nvidia-cuda-runtime-cu12 nvidia-cublas-cu12 nvidia-cufft-cu12 `
            nvidia-curand-cu12 nvidia-cusolver-cu12 nvidia-cusparse-cu12 `
            nvidia-cudnn-cu12
```

Why two CUDA versions? Torch ships its own CUDA 13 runtime; `onnxruntime-gpu`
1.26 is built against CUDA 12 + cuDNN 9. They coexist fine — they just live in
different folders inside `site-packages/nvidia/`.

[`backend/app/processing/ai.py`](backend/app/processing/ai.py) auto-detects
those bundled NVIDIA DLL directories at import time and prepends them to
`PATH` (cuDNN's engine sublibs like `cudnn_engines_tensor_ir64_9.dll` are
loaded via `LoadLibraryA`, which ignores `os.add_dll_directory`). The CUDA EP
is preferred when available; DirectML is the fallback for non-NVIDIA GPUs.
TensorRT is skipped by default — set `EAP_ENABLE_TRT=1` if you have a full
TensorRT install.

---

## Workflow in the UI

1. **Projects** — create or open a project
2. **Import** — drop lights (and optionally darks / flats / bias)
3. **Stack** — pick a stacking method; tick "Calibrate" to use master frames
4. **Background** — remove gradients / light pollution
5. **Denoise** → **Sharpen**
6. **Stretch** — non-destructive; replays from the master
7. **Color** — natural RGB or Hubble palettes
8. **Stars** — generate a star mask / starless preview / reduce stars
9. **Pixel Math** — custom expressions when you need them
10. **Export** — PNG / JPEG / 16-bit TIFF / 32-bit FITS

The **Recipe** panel (top bar) lets you toggle steps, delete them, replay the
whole pipeline, or save / load the recipe as JSON. Original frames and the
master stack are never modified.

---

## Headless CLI

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m app.cli new-project --name "M33" --target galaxy
python -m app.cli import-frames <project-id> --type light "C:\Captures\m33\lights\*.fit"
python -m app.cli import-frames <project-id> --type dark  "C:\Captures\m33\darks\*.fit"
python -m app.cli stack <project-id> --method sigma_clip --calibrate
python -m app.cli run-recipe <project-id> --recipe my-recipe.json
python -m app.cli export <project-id> --format tif
```

---

## Repository layout

```
EasyAstroPhoto/
  backend/        FastAPI service + Python processing engine
    app/
      api/        HTTP routers (projects, frames, processing, ai)
      processing/ Image engine (calibration, registration, stacking,
                  background, denoise, deconvolution, stretch, color,
                  stars, pixel_math, ai)
      services/   Project / frame / job / recipe orchestration
      cli.py      Headless CLI
    scripts/
      download_models.py   Lists curated ONNX model sources
  frontend/       React + Vite + TypeScript UI (workflow rail, controls,
                  AI manager modal, recipe panel, split-slider viewer)
  models/         Local ONNX model directory (used by the backend; gitignored)
```

---

## Troubleshooting

**`Stack failed: 500 Internal Server Error` right after restarting the backend.**
Likely a stale uvicorn process is still bound to the old port. Find and kill
the leaked listener:

```powershell
netstat -ano | findstr :8766
taskkill /F /PID <pid>
```

If the PID shows as already gone but the port is still held, reboot or pick a
different port (and remember to update `frontend/vite.config.ts`).

**`404 Not Found` on every API call.** Something else is already bound to
8766. Confirm with `netstat -ano | findstr :8766` — if it's a different
program, change EAP's port.

**AI Models panel says "GPU available: no" but I have a GPU.** Install
`onnxruntime-directml` (or `onnxruntime-gpu` if you have a matching CUDA setup)
in the backend venv and restart uvicorn. See "Phase 5" above.

---

## License

MIT (placeholder — choose a license before publishing).
