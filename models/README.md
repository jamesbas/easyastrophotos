# ONNX models go here

The Easy Astro Photos backend looks for `.onnx` files in this folder by default
(when running from a checkout). You can override the location with the
`EAP_MODELS_DIR` environment variable.

## Naming convention

The backend picks a default model for each AI operation by **prefix**:

| Filename starts with | Used by                 | Backend feature                |
| -------------------- | ----------------------- | ------------------------------ |
| `denoise*.onnx`      | Denoise → method "ai"   | Noise reduction                |
| `background*.onnx`   | Background → method "ai"| Light-pollution / gradient AI  |
| `decon*.onnx`        | Sharpen → method "ai"   | AI deconvolution / sharpening  |

If multiple files match a prefix, the first one (alphabetical) is used. You can
also pass an explicit `model_name` from the UI's Advanced controls to pick a
specific file.

## I/O contract

The backend treats every model as a single-input / single-output network with:

- input  : `float32`, shape `NCHW` or `NHWC`, value range `[0, 1]`
- output : same shape, same range

Color images are passed as 3 channels (RGB). Mono is passed as 1 channel.

## Where do I get models?

**Honest answer:** there is *not* a freely-redistributable, production-grade set
of astrophotography-specific ONNX models on HuggingFace. The well-known ones
(`NoiseXTerminator`, `StarXTerminator`, `BlurXTerminator` by RC-Astro) are
commercial — buy them from <https://www.rc-astro.com>. They are not ONNX and
won't load here directly even if you own them.

> [!IMPORTANT]
> **No model binaries ship with the repository.** This folder is gitignored
> for `*.onnx`, `*.onnx.data`, `*.pt`, `*.pth`, `*.bin`, and `*.safetensors`,
> so a fresh clone has zero models. Run the conversion script below to
> populate it locally.

For the AI hooks in this app you have three realistic options:

### 1. Convert SCUNet automatically (recommended)

[`backend/scripts/convert_scunet.py`](../backend/scripts/convert_scunet.py)
downloads the official SCUNet weights (Apache 2.0, Zhang et al.) and exports
them to ONNX. Run from the project root with the backend venv active:

```powershell
cd backend
# torch wheel — pick the right index for your GPU:
pip install torch --index-url https://download.pytorch.org/whl/cu130   # RTX 50xx
# or  pip install torch --index-url https://download.pytorch.org/whl/cu121  # other NVIDIA
# or  pip install torch                                                      # CPU-only
# SCUNet network module + new dynamo ONNX exporter:
pip install einops timm thop onnxscript
python scripts/convert_scunet.py
```

The script downloads `scunet_color_real_psnr.pth` (~72 MB, Apache 2.0) from
the official KAIR releases into `backend/.cache/scunet/`, then exports to
this folder as a pair of files:

- `denoise_scunet_color.onnx` (~3.7 MB graph)
- `denoise_scunet_color.onnx.data` (~73 MB external weights)

ONNX Runtime loads them together — keep both in the same folder. The Easy
Astro Photos backend picks them up automatically the next time you choose
the "AI" denoise method. Variants: `--variant color_real_gan` (more
aggressive), `--variant gray_25` (mono frames).

> SCUNet was trained on natural photos. It's surprisingly effective on
> *post-stretch* astro data, where the noise grain looks more like camera
> sensor noise. On linear (pre-stretch) data it's much weaker — use the
> built-in starlet denoiser instead.
>
> Measured throughput: ~11 s per 3000 × 4500 RGB frame on an RTX 5070 Ti via
> CUDA EP with 256-px tiled inference.

### 2. Convert a different pretrained denoiser to ONNX

General image denoisers like **DRUNet** and **FFDNet** by Kai Zhang are also
MIT/Apache licensed. The `convert_scunet.py` script can be adapted to them
without much trouble.

### 3. Train your own (eventually)

The repo has a training scaffold roadmap (see `Astro App Design Requirements.md`)
for an astro-specific U-Net — but expect this to be a project of its own,
requiring a GPU and your own dataset.

## Helper script

[`backend/scripts/download_models.py`](../backend/scripts/download_models.py)
prints a curated list of starting points. It does **not** auto-download
proprietary or unverified weights.
