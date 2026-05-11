import { useEffect, useState } from "react";
import type { Project, TargetType } from "../types";
import { api } from "../api";

interface Props {
  onClose: () => void;
  onPick: (p: Project) => void;
  onCreate: (name: string, target: TargetType) => Promise<void>;
  activeId?: string;
  notify: (msg: string, kind?: "success" | "error") => void;
}

const TARGETS: { id: TargetType; label: string }[] = [
  { id: "unknown", label: "Unknown / auto-detect" },
  { id: "nebula", label: "Nebula" },
  { id: "galaxy", label: "Galaxy" },
  { id: "cluster", label: "Star cluster" },
  { id: "moon_planetary", label: "Moon / planetary" },
  { id: "milky_way", label: "Milky Way / widefield" }
];

export function ProjectPickerModal({
  onClose,
  onPick,
  onCreate,
  activeId,
  notify
}: Props) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState("");
  const [target, setTarget] = useState<TargetType>("unknown");
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      const list = await api.listProjects();
      setProjects(list);
    } catch (e) {
      notify(`Cannot reach backend: ${(e as Error).message}`, "error");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function create() {
    if (!name.trim()) return;
    setBusy(true);
    try {
      await onCreate(name.trim(), target);
      setName("");
    } catch (e) {
      notify(`Create failed: ${(e as Error).message}`, "error");
    } finally {
      setBusy(false);
    }
  }

  async function deleteProject(id: string, e: React.MouseEvent) {
    e.stopPropagation();
    if (!confirm("Delete this project and all its data?")) return;
    try {
      await api.deleteProject(id);
      await refresh();
    } catch (err) {
      notify(`Delete failed: ${(err as Error).message}`, "error");
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Projects</h2>

        <div className="group">
          <div className="muted">Create new project</div>
          <div className="row">
            <input
              placeholder="Project name…"
              value={name}
              onChange={(e) => setName(e.target.value)}
              style={{ flex: 1 }}
              onKeyDown={(e) => e.key === "Enter" && create()}
            />
          </div>
          <div className="row">
            <select
              value={target}
              onChange={(e) => setTarget(e.target.value as TargetType)}
              style={{ flex: 1 }}
            >
              {TARGETS.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.label}
                </option>
              ))}
            </select>
            <button className="primary" onClick={create} disabled={busy || !name.trim()}>
              Create
            </button>
          </div>
        </div>

        <div className="muted">Recent projects</div>
        <div className="project-list" style={{ maxHeight: 280, overflowY: "auto" }}>
          {projects.length === 0 && (
            <div className="muted" style={{ padding: 8 }}>
              No projects yet.
            </div>
          )}
          {projects.map((p) => (
            <div
              key={p.project_id}
              className="project-item"
              style={
                p.project_id === activeId
                  ? { borderColor: "var(--accent)" }
                  : undefined
              }
              onClick={() => onPick(p)}
            >
              <div className="name">{p.name}</div>
              <div className="when">
                {new Date(p.updated_at).toLocaleString()}
              </div>
              <button className="danger" onClick={(e) => deleteProject(p.project_id, e)}>
                Delete
              </button>
            </div>
          ))}
        </div>

        <div className="actions">
          <button onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
