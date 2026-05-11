export type TargetType =
  | "galaxy"
  | "nebula"
  | "cluster"
  | "moon_planetary"
  | "milky_way"
  | "unknown";

export type FrameType = "light" | "dark" | "flat" | "bias" | "flat_dark";

export interface Project {
  project_id: string;
  name: string;
  target_type: TargetType;
  created_at: string;
  updated_at: string;
  status: string;
  has_stack: boolean;
  has_preview: boolean;
}

export interface Frame {
  frame_id: string;
  project_id: string;
  original_name: string;
  frame_type: FrameType;
  width?: number | null;
  height?: number | null;
  bit_depth?: number | null;
  quality_score?: number | null;
  star_count?: number | null;
  included: boolean;
  created_at: string;
}

export interface JobResult {
  ok: boolean;
  message: string;
  details: Record<string, unknown>;
}

export interface RecipeStep {
  id: string;
  operation: string;
  params: Record<string, unknown>;
  enabled?: boolean;
  ts?: number;
}

export interface Recipe {
  project_id: string;
  steps: RecipeStep[];
}

export interface AiModel {
  name: string;
  filename: string;
  path: string;
  size_bytes: number;
}

export interface AiRuntime {
  onnxruntime_available: boolean;
  providers: string[];
  gpu: boolean;
  version?: string;
  error?: string;
}

// ----- Operation option payloads -----

export interface CalibrateOptions {
  use_darks: boolean;
  use_flats: boolean;
  use_bias: boolean;
  cosmetic_correction: boolean;
  dark_optimization: boolean;
  flat_normalization: "mean" | "median";
  master_method: "median" | "average" | "sigma_clip";
}

export interface StackOptions {
  method:
    | "average"
    | "median"
    | "weighted_average"
    | "sigma_clip"
    | "winsorized_sigma_clip"
    | "minmax_reject";
  align: boolean;
  weighting: "equal" | "quality" | "stars" | "noise";
  sigma_low: number;
  sigma_high: number;
  calibrate: boolean;
  calibration: CalibrateOptions;
}

export interface StretchOptions {
  method: "asinh" | "percentile" | "histogram" | "ghs" | "curves";
  black_point: number;
  midtone: number;
  white_point: number;
  protect_highlights: boolean;
  protect_shadows: boolean;
  stretch_factor: number;
  local_intensity: number;
}

export interface BackgroundOptions {
  method: "polynomial" | "rbf" | "ai";
  degree: number;
  smoothing: number;
  correction: "subtraction" | "division";
  strength: number;
  protect_objects: boolean;
  samples: number;
  sample_percentile?: number;
  sigma_high?: number;
  rejection_iters?: number;
}

export interface DenoiseOptions {
  method: "nlm" | "wavelet" | "starlet" | "bilateral" | "ai";
  strength: number;
  protect_stars: boolean;
  scales?: number;
  preserve_coarse?: boolean;
  model_name?: string | null;
}

export interface DeconvolutionOptions {
  method: "richardson_lucy" | "wiener" | "unsharp" | "ai";
  strength: number;
  fwhm: number; // 0 = auto-estimate
  iterations: number;
  star_mode: boolean;
  protect_ringing: boolean;
  tv_lambda?: number;
  model_name?: string | null;
}

export interface ColorOptions {
  mode: "natural_rgb" | "sho" | "hoo" | "custom";
  saturation: number;
  green_reduction: number;
  background_neutralization: boolean;
  preserve_star_color: boolean;
  channel_map: Record<string, string>;
}
