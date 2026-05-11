import { useState } from "react";
import type { Project, TargetType } from "./types";
import { api } from "./api";
import { WorkflowRail } from "./components/WorkflowRail";
import { ImportPanel } from "./components/ImportPanel";
import { ImageViewer } from "./components/ImageViewer";
import { ControlsPanel } from "./components/ControlsPanel";
import { ProjectPickerModal } from "./components/ProjectPickerModal";
import { Toast } from "./components/Toast";
import { AiManagerModal } from "./components/AiManagerModal";
import { RecipePanel } from "./components/RecipePanel";

export type Step =
  | "import"
  | "calibrate"
  | "align"
  | "stack"
  | "background"
  | "denoise"
  | "deconvolution"
  | "stretch"
  | "color"
  | "stars"
  | "pixel_math"
  | "export";

export function App() {
  const [project, setProject] = useState<Project | null>(null);
  const [step, setStep] = useState<Step>("import");
  const [pickerOpen, setPickerOpen] = useState(true);
  const [aiOpen, setAiOpen] = useState(false);
  const [advanced, setAdvanced] = useState(false);
  const [recipeOpen, setRecipeOpen] = useState(false);
  const [toast, setToast] = useState<{ msg: string; kind: "success" | "error" } | null>(null);
  const [previewVersion, setPreviewVersion] = useState(0);
  const [busy, setBusy] = useState(false);
  const [overlay, setOverlay] = useState<"none" | "star_mask" | "starless" | "background_model">("none");

  function notify(msg: string, kind: "success" | "error" = "success") {
    setToast({ msg, kind });
    setTimeout(() => setToast(null), 3500);
  }

  async function selectProject(p: Project) {
    const fresh = await api.getProject(p.project_id);
    setProject(fresh);
    setPickerOpen(false);
    setStep(fresh.has_preview ? "stretch" : "import");
    setPreviewVersion((v) => v + 1);
  }

  async function createProject(name: string, target: TargetType) {
    const p = await api.createProject(name, target);
    await selectProject(p);
  }

  async function refreshProject() {
    if (!project) return;
    const fresh = await api.getProject(project.project_id);
    setProject(fresh);
    setPreviewVersion((v) => v + 1);
  }

  return (
    <div className="app">
      <header className="topbar">
        <h1>Easy Astro Photos</h1>
        {project && (
          <span className="project-pill">
            {project.name}
            <span style={{ color: "var(--text-dim)" }}> · {project.target_type}</span>
          </span>
        )}
        <div className="spacer" />
        <label className="row" style={{ gap: 6 }}>
          <input
            type="checkbox"
            checked={advanced}
            onChange={(e) => setAdvanced(e.target.checked)}
          />
          <span className="muted">Advanced mode</span>
        </label>
        <button onClick={() => setAiOpen(true)}>AI Models</button>
        <button onClick={() => setRecipeOpen((v) => !v)} disabled={!project}>
          {recipeOpen ? "Hide Recipe" : "Show Recipe"}
        </button>
        <button onClick={() => setPickerOpen(true)}>Projects</button>
      </header>

      <div className="main">
        <WorkflowRail step={step} onSelect={setStep} hasStack={!!project?.has_stack} hasPreview={!!project?.has_preview} hasProject={!!project} />

        <div className="viewer">
          <ImageViewer
            project={project}
            previewVersion={previewVersion}
            step={step}
            overlay={overlay}
            onOverlayChange={setOverlay}
          />
        </div>

        <aside className="controls">
          {!project && (
            <div className="empty-state">
              <div>Create or open a project to begin.</div>
              <button className="primary" onClick={() => setPickerOpen(true)}>
                Open Projects
              </button>
            </div>
          )}
          {project && step === "import" && (
            <ImportPanel project={project} onChanged={refreshProject} notify={notify} advanced={advanced} />
          )}
          {project && step !== "import" && (
            <ControlsPanel
              project={project}
              step={step}
              busy={busy}
              setBusy={setBusy}
              advanced={advanced}
              onChanged={refreshProject}
              notify={notify}
              onAdvance={(next) => setStep(next)}
              setOverlay={setOverlay}
            />
          )}
          {project && recipeOpen && (
            <RecipePanel project={project} onChanged={refreshProject} notify={notify} />
          )}
        </aside>
      </div>

      {pickerOpen && (
        <ProjectPickerModal
          onClose={() => setPickerOpen(false)}
          onPick={selectProject}
          onCreate={createProject}
          activeId={project?.project_id}
          notify={notify}
        />
      )}
      {aiOpen && <AiManagerModal onClose={() => setAiOpen(false)} notify={notify} />}
      {toast && <Toast kind={toast.kind} message={toast.msg} />}
    </div>
  );
}
