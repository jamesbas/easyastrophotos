import { useCallback, useEffect, useState } from "react";
import type { Frame, FrameType, Project } from "../types";
import { api } from "../api";

interface Props {
  project: Project;
  onChanged: () => void;
  notify: (msg: string, kind?: "success" | "error") => void;
  advanced: boolean;
}

const FRAME_TYPES: { id: FrameType; title: string; help: string; required?: boolean }[] = [
  { id: "light", title: "Light Frames", help: "The actual sky exposures of your target.", required: true },
  { id: "dark", title: "Dark Frames", help: "Same exposure & temperature, lens cap on. Removes thermal noise." },
  { id: "flat", title: "Flat Frames", help: "Uniform light source. Removes vignetting and dust." },
  { id: "bias", title: "Bias / Flat Darks", help: "Very short exposures. Removes camera readout signal." }
];

export function ImportPanel({ project, onChanged, notify }: Props) {
  return (
    <>
      {FRAME_TYPES.map((ft) => (
        <FramesGroup
          key={ft.id}
          project={project}
          onChanged={onChanged}
          notify={notify}
          frameType={ft.id}
          title={ft.title}
          help={ft.help}
          required={ft.required}
        />
      ))}
    </>
  );
}

function FramesGroup({
  project,
  onChanged,
  notify,
  frameType,
  title,
  help,
  required
}: {
  project: Project;
  onChanged: () => void;
  notify: (msg: string, kind?: "success" | "error") => void;
  frameType: FrameType;
  title: string;
  help: string;
  required?: boolean;
}) {
  const [frames, setFrames] = useState<Frame[]>([]);
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const list = await api.listFrames(project.project_id, frameType);
    setFrames(list);
  }, [project.project_id, frameType]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function uploadFiles(fileList: FileList | File[]) {
    const files = Array.from(fileList);
    if (!files.length) return;
    setBusy(true);
    try {
      const created = await api.uploadFrames(project.project_id, files, frameType);
      notify(`Imported ${created.length} ${title.toLowerCase()}`);
      await refresh();
      onChanged();
    } catch (e) {
      notify(`Import failed: ${(e as Error).message}`, "error");
    } finally {
      setBusy(false);
    }
  }

  async function removeFrame(id: string) {
    await api.deleteFrame(project.project_id, id);
    await refresh();
    onChanged();
  }

  async function toggleIncluded(f: Frame) {
    await api.setFrameIncluded(project.project_id, f.frame_id, !f.included);
    await refresh();
  }

  return (
    <div className="group">
      <h2>
        {title} {required && <span style={{ color: "var(--warn)" }}>*</span>}
      </h2>
      <p className="muted" style={{ margin: 0 }}>{help}</p>
      <label
        className={`dropzone${drag ? " drag" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          if (e.dataTransfer.files) uploadFiles(e.dataTransfer.files);
        }}
      >
        <input
          type="file"
          multiple
          style={{ display: "none" }}
          accept=".fit,.fits,.fts,.tif,.tiff,.png,.jpg,.jpeg"
          onChange={(e) => e.target.files && uploadFiles(e.target.files)}
        />
        {busy ? (
          <span><span className="spinner" /> Importing…</span>
        ) : (
          <>
            <div style={{ fontWeight: 600 }}>Drop {title} Here</div>
            <div style={{ fontSize: 12 }}>or click to browse</div>
          </>
        )}
      </label>
      <div className="row between">
        <span className="muted">{frames.length} frame{frames.length === 1 ? "" : "s"}</span>
        {required && frames.length === 0 && (
          <span className="muted">At least 2 needed to stack</span>
        )}
      </div>
      {frames.length > 0 && (
        <div className="frame-list">
          {frames.map((f) => (
            <div
              key={f.frame_id}
              className={`frame-card${f.included ? "" : " excluded"}`}
              title={`${f.original_name}${
                f.quality_score != null ? ` · score ${f.quality_score.toFixed(2)}` : ""
              }${f.star_count != null ? ` · ${f.star_count}★` : ""}\nClick to ${f.included ? "exclude" : "include"}`}
              onClick={() => toggleIncluded(f)}
            >
              <span className="x" onClick={(e) => { e.stopPropagation(); removeFrame(f.frame_id); }}>×</span>
              <img src={api.thumbnailUrl(project.project_id, f.frame_id)} alt={f.original_name} />
              <div className="meta">
                <span>{f.star_count ?? "—"}★</span>
                <span>{f.quality_score != null ? f.quality_score.toFixed(2) : "—"}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
