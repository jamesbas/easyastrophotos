import type {
  AiModel,
  AiRuntime,
  BackgroundOptions,
  ColorOptions,
  DeconvolutionOptions,
  DenoiseOptions,
  Frame,
  FrameType,
  JobResult,
  Project,
  Recipe,
  StackOptions,
  StretchOptions,
  TargetType
} from "./types";

const BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status}: ${detail || res.statusText}`);
  }
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return (await res.json()) as T;
  return (await res.text()) as unknown as T;
}

function postJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body)
  });
}

export const api = {
  // Projects ------------------------------------------------------------------
  listProjects: () => request<Project[]>("/projects"),
  createProject: (name: string, target_type: TargetType) =>
    postJson<Project>("/projects", { name, target_type }),
  getProject: (id: string) => request<Project>(`/projects/${id}`),
  deleteProject: (id: string) =>
    request<{ ok: boolean }>(`/projects/${id}`, { method: "DELETE" }),

  // Frames --------------------------------------------------------------------
  listFrames: (id: string, frameType?: FrameType) =>
    request<Frame[]>(
      `/projects/${id}/frames${frameType ? `?frame_type=${frameType}` : ""}`
    ),
  uploadFrames: async (id: string, files: File[], frameType: FrameType) => {
    const fd = new FormData();
    for (const f of files) fd.append("files", f, f.name);
    fd.append("frame_type", frameType);
    const res = await fetch(`${BASE}/projects/${id}/frames`, {
      method: "POST",
      body: fd
    });
    if (!res.ok) throw new Error(await res.text());
    return (await res.json()) as Frame[];
  },
  deleteFrame: (projectId: string, frameId: string) =>
    request<{ ok: boolean }>(`/projects/${projectId}/frames/${frameId}`, {
      method: "DELETE"
    }),
  setFrameIncluded: (projectId: string, frameId: string, included: boolean) =>
    request<Frame>(
      `/projects/${projectId}/frames/${frameId}?included=${included}`,
      { method: "PATCH" }
    ),

  // Processing ----------------------------------------------------------------
  stack: (projectId: string, options: Partial<StackOptions>) =>
    postJson<JobResult>(`/projects/${projectId}/jobs/stack`, options),
  calibrate: (projectId: string, options: Record<string, unknown>) =>
    postJson<JobResult>(`/projects/${projectId}/jobs/calibrate`, options),
  stretch: (projectId: string, options: Partial<StretchOptions>) =>
    postJson<JobResult>(`/projects/${projectId}/jobs/stretch`, options),
  background: (projectId: string, options: Partial<BackgroundOptions>) =>
    postJson<JobResult>(
      `/projects/${projectId}/jobs/background-extraction`,
      options
    ),
  denoise: (projectId: string, options: Partial<DenoiseOptions>) =>
    postJson<JobResult>(`/projects/${projectId}/jobs/denoise`, options),
  deconvolve: (projectId: string, options: Partial<DeconvolutionOptions>) =>
    postJson<JobResult>(`/projects/${projectId}/jobs/deconvolution`, options),
  color: (projectId: string, options: Partial<ColorOptions>) =>
    postJson<JobResult>(`/projects/${projectId}/jobs/colorize`, options),
  starReduction: (projectId: string, amount: number) =>
    postJson<JobResult>(`/projects/${projectId}/jobs/star-reduction`, { amount }),
  starMask: (projectId: string) =>
    request<JobResult>(`/projects/${projectId}/jobs/star-mask`, {
      method: "POST"
    }),
  starless: (projectId: string) =>
    request<JobResult>(`/projects/${projectId}/jobs/starless`, {
      method: "POST"
    }),
  pixelMath: (projectId: string, expression: string, persist = true) =>
    postJson<JobResult>(`/projects/${projectId}/jobs/pixel-math`, {
      expression,
      persist
    }),
  exportImage: (projectId: string, fmt: "png" | "tif" | "fit" | "jpg") =>
    request<JobResult>(`/projects/${projectId}/jobs/export?fmt=${fmt}`, {
      method: "POST"
    }),

  // Recipe --------------------------------------------------------------------
  getRecipe: (projectId: string) =>
    request<Recipe>(`/projects/${projectId}/recipe`),
  replayRecipe: (projectId: string) =>
    request<JobResult>(`/projects/${projectId}/recipe/replay`, {
      method: "POST"
    }),
  removeRecipeStep: (projectId: string, stepId: string) =>
    request<{ ok: boolean }>(`/projects/${projectId}/recipe/steps/${stepId}`, {
      method: "DELETE"
    }),
  setRecipeStepEnabled: (projectId: string, stepId: string, enabled: boolean) =>
    request<{ ok: boolean }>(
      `/projects/${projectId}/recipe/steps/${stepId}`,
      {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ enabled })
      }
    ),
  importRecipe: (projectId: string, steps: unknown[]) =>
    postJson<JobResult>(`/projects/${projectId}/recipe/import`, { steps }),

  // AI ------------------------------------------------------------------------
  aiRuntime: () => request<AiRuntime>("/ai/runtime"),
  aiListModels: () =>
    request<{ models_dir: string; models: AiModel[] }>("/ai/models"),
  aiUploadModel: async (file: File) => {
    const fd = new FormData();
    fd.append("file", file, file.name);
    const res = await fetch(`${BASE}/ai/models`, { method: "POST", body: fd });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
  aiDeleteModel: (name: string) =>
    request<{ ok: boolean }>(`/ai/models/${encodeURIComponent(name)}`, {
      method: "DELETE"
    }),

  // Preview URLs --------------------------------------------------------------
  thumbnailUrl: (projectId: string, frameId: string) =>
    `${BASE}/projects/${projectId}/frames/${frameId}/thumbnail`,
  originalPreviewUrl: (projectId: string, v: number) =>
    `${BASE}/projects/${projectId}/preview/original?t=${v}`,
  currentPreviewUrl: (projectId: string, v: number) =>
    `${BASE}/projects/${projectId}/preview/current?t=${v}`,
  starMaskUrl: (projectId: string, v: number) =>
    `${BASE}/projects/${projectId}/preview/star-mask?t=${v}`,
  starlessUrl: (projectId: string, v: number) =>
    `${BASE}/projects/${projectId}/preview/starless?t=${v}`,
  backgroundModelUrl: (projectId: string, v: number) =>
    `${BASE}/projects/${projectId}/preview/background-model?t=${v}`,
  exportFileUrl: (
    projectId: string,
    fmt: "png" | "tif" | "fit" | "jpg"
  ) => `${BASE}/projects/${projectId}/export/file?fmt=${fmt}`
};
