"""Pydantic models for the public API."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field


TargetType = Literal[
    "galaxy", "nebula", "cluster", "moon_planetary", "milky_way", "unknown"
]
FrameType = Literal["light", "dark", "flat", "bias", "flat_dark"]


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    target_type: TargetType = "unknown"


class ProjectOut(BaseModel):
    project_id: str
    name: str
    target_type: TargetType
    created_at: str
    updated_at: str
    status: str
    has_stack: bool
    has_preview: bool


class FrameOut(BaseModel):
    frame_id: str
    project_id: str
    original_name: str
    frame_type: FrameType
    width: Optional[int] = None
    height: Optional[int] = None
    bit_depth: Optional[int] = None
    quality_score: Optional[float] = None
    star_count: Optional[int] = None
    included: bool
    created_at: str


class CalibrateOptions(BaseModel):
    use_darks: bool = True
    use_flats: bool = True
    use_bias: bool = True
    cosmetic_correction: bool = True
    dark_optimization: bool = False
    flat_normalization: Literal["mean", "median"] = "mean"
    master_method: Literal["median", "average", "sigma_clip"] = "median"


class StackOptions(BaseModel):
    method: Literal[
        "average", "median", "weighted_average", "sigma_clip",
        "winsorized_sigma_clip", "minmax_reject"
    ] = "average"
    align: bool = True
    weighting: Literal["equal", "quality", "stars", "noise"] = "equal"
    sigma_low: float = 3.0
    sigma_high: float = 3.0
    calibrate: bool = False
    calibration: CalibrateOptions = CalibrateOptions()


class StretchOptions(BaseModel):
    method: Literal["asinh", "percentile", "histogram", "ghs", "curves"] = "asinh"
    black_point: float = Field(default=0.001, ge=0.0, le=1.0)
    midtone: float = Field(default=0.25, ge=0.001, le=0.999)
    white_point: float = Field(default=1.0, ge=0.0, le=1.0)
    protect_highlights: bool = True
    protect_shadows: bool = True
    stretch_factor: float = 4.0
    local_intensity: float = 0.5
    curve_points: Optional[List[Tuple[float, float]]] = None


class BackgroundOptions(BaseModel):
    method: Literal["polynomial", "rbf", "ai"] = "rbf"
    degree: int = 4
    smoothing: float = 0.5
    correction: Literal["subtraction", "division"] = "subtraction"
    strength: float = 1.0
    protect_objects: bool = True
    samples: int = 32
    sample_percentile: float = 20.0
    sigma_high: float = 2.5
    rejection_iters: int = 3


class DenoiseOptions(BaseModel):
    method: Literal["nlm", "wavelet", "starlet", "bilateral", "ai"] = "starlet"
    strength: float = 0.45
    protect_stars: bool = True
    scales: int = 5
    preserve_coarse: bool = True
    model_name: Optional[str] = None


class DeconvolutionOptions(BaseModel):
    method: Literal["richardson_lucy", "wiener", "unsharp", "ai"] = "richardson_lucy"
    strength: float = 0.5
    fwhm: float = 0.0  # 0 = auto-estimate from stars
    iterations: int = 20
    star_mode: bool = False
    protect_ringing: bool = True
    tv_lambda: float = 0.002
    model_name: Optional[str] = None


class ColorOptions(BaseModel):
    mode: Literal["natural_rgb", "sho", "hoo", "custom"] = "natural_rgb"
    saturation: float = 0.0
    green_reduction: float = 0.0
    background_neutralization: bool = True
    preserve_star_color: bool = True
    channel_map: Dict[str, str] = {}


class StarReductionOptions(BaseModel):
    amount: float = Field(default=0.5, ge=0.0, le=1.0)


class PixelMathRequest(BaseModel):
    expression: str
    persist: bool = True


class RecipeStepUpdate(BaseModel):
    enabled: bool


class RecipeApplyRequest(BaseModel):
    steps: List[Dict[str, Any]]


class JobResult(BaseModel):
    ok: bool
    message: str
    details: Dict[str, Any] = {}
