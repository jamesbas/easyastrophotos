import { useCallback, useEffect, useState } from "react";
import type { Project, Recipe } from "../types";
import { api } from "../api";

interface Props {
  project: Project;
  onChanged: () => void;
  notify: (msg: string, kind?: "success" | "error") => void;
}

export function RecipePanel({ project, onChanged, notify }: Props) {
  const [recipe, setRecipe] = useState<Recipe | null>(null);

  const refresh = useCallback(async () => {
    setRecipe(await api.getRecipe(project.project_id));
  }, [project.project_id]);

  useEffect(() => { refresh(); }, [refresh]);

  async function toggleStep(stepId: string, enabled: boolean) {
    await api.setRecipeStepEnabled(project.project_id, stepId, enabled);
    await api.replayRecipe(project.project_id);
    onChanged();
    refresh();
  }
  async function removeStep(stepId: string) {
    await api.removeRecipeStep(project.project_id, stepId);
    await api.replayRecipe(project.project_id);
    onChanged();
    refresh();
  }
  async function replay() {
    try { await api.replayRecipe(project.project_id); notify("Recipe replayed"); onChanged(); }
    catch (e) { notify(`Replay failed: ${(e as Error).message}`, "error"); }
  }
  function downloadRecipe() {
    if (!recipe) return;
    const blob = new Blob([JSON.stringify(recipe, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `${project.name}-recipe.json`; a.click();
    URL.revokeObjectURL(url);
  }
  async function importFile(files: FileList | null) {
    if (!files || !files[0]) return;
    try {
      const text = await files[0].text();
      const data = JSON.parse(text);
      const steps = Array.isArray(data) ? data : (data.steps || []);
      await api.importRecipe(project.project_id, steps);
      notify("Recipe imported & replayed");
      onChanged();
      refresh();
    } catch (e) { notify(`Import failed: ${(e as Error).message}`, "error"); }
  }

  return (
    <div className="group">
      <h2>Processing Recipe</h2>
      <p className="muted" style={{ margin: 0 }}>
        Every operation is non-destructive. Toggle steps off to compare, or replay
        the entire recipe from the master stack.
      </p>
      <div className="row" style={{ flexWrap: "wrap", gap: 6 }}>
        <button onClick={replay}>Replay all</button>
        <button onClick={downloadRecipe}>Export JSON</button>
        <label className="dropzone" style={{ padding: 8 }}>
          <input type="file" accept="application/json" style={{ display: "none" }}
                 onChange={(e) => importFile(e.target.files)} />
          Import JSON
        </label>
      </div>
      {recipe && recipe.steps.length === 0 && <span className="muted">No steps yet.</span>}
      {recipe && recipe.steps.map((s, i) => (
        <div key={s.id} className="row between" style={{ background: "var(--bg-2)", padding: 8, borderRadius: 6, border: "1px solid var(--border)" }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 500 }}>{i + 1}. {s.operation}</div>
            <div className="muted" style={{ fontSize: 11, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {Object.entries(s.params || {}).slice(0, 3).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ")}
            </div>
          </div>
          <label className="row" style={{ gap: 4 }}>
            <input type="checkbox" checked={s.enabled !== false} onChange={(e) => toggleStep(s.id, e.target.checked)} />
            <span className="muted">on</span>
          </label>
          <button className="danger" onClick={() => removeStep(s.id)}>×</button>
        </div>
      ))}
    </div>
  );
}
