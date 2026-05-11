import { useEffect, useState } from "react";
import type { AiModel, AiRuntime } from "../types";
import { api } from "../api";

interface Props {
  onClose: () => void;
  notify: (msg: string, kind?: "success" | "error") => void;
}

export function AiManagerModal({ onClose, notify }: Props) {
  const [runtime, setRuntime] = useState<AiRuntime | null>(null);
  const [models, setModels] = useState<AiModel[]>([]);
  const [modelsDir, setModelsDir] = useState<string>("");

  async function refresh() {
    try {
      setRuntime(await api.aiRuntime());
      const r = await api.aiListModels();
      setModels(r.models);
      setModelsDir(r.models_dir);
    } catch (e) {
      notify(`AI info failed: ${(e as Error).message}`, "error");
    }
  }
  useEffect(() => { refresh(); }, []);

  async function upload(files: FileList | null) {
    if (!files) return;
    for (const f of Array.from(files)) {
      try { await api.aiUploadModel(f); notify(`Uploaded ${f.name}`); }
      catch (e) { notify(`Upload failed: ${(e as Error).message}`, "error"); }
    }
    refresh();
  }

  async function remove(name: string) {
    if (!confirm(`Delete model ${name}?`)) return;
    await api.aiDeleteModel(name);
    refresh();
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ width: 520 }}>
        <h2>AI Models (Phase 5)</h2>
        <div className="group">
          <h2>Runtime</h2>
          {!runtime ? <span className="muted">Loading…</span> : (
            <>
              <div className="row between"><span>onnxruntime installed</span><span>{runtime.onnxruntime_available ? "yes" : "no"}</span></div>
              {runtime.version && <div className="row between"><span>Version</span><span>{runtime.version}</span></div>}
              <div className="row between"><span>GPU available</span><span>{runtime.gpu ? "yes" : "no"}</span></div>
              {runtime.providers.length > 0 && <div className="muted">Providers: {runtime.providers.join(", ")}</div>}
              {!runtime.onnxruntime_available && (
                <p className="muted" style={{ margin: 0 }}>
                  Install <code>onnxruntime</code> (CPU), <code>onnxruntime-gpu</code>, or
                  <code> onnxruntime-directml</code> in the backend env to enable AI features.
                </p>
              )}
            </>
          )}
        </div>

        <div className="group">
          <h2>Installed Models</h2>
          <div className="muted" style={{ wordBreak: "break-all" }}>{modelsDir}</div>
          {models.length === 0 && <span className="muted">No models installed.</span>}
          {models.map((m) => (
            <div key={m.name} className="row between">
              <span>{m.filename}</span>
              <span className="muted">{(m.size_bytes / (1024 * 1024)).toFixed(1)} MB</span>
              <button className="danger" onClick={() => remove(m.filename)}>Delete</button>
            </div>
          ))}
          <label className="dropzone">
            <input type="file" accept=".onnx" multiple style={{ display: "none" }}
                   onChange={(e) => upload(e.target.files)} />
            Drop / select <code>.onnx</code> files
          </label>
          <p className="muted" style={{ margin: 0 }}>
            Naming convention picks defaults: <code>denoise*.onnx</code>, <code>background*.onnx</code>, <code>decon*.onnx</code>.
          </p>
        </div>

        <div className="actions"><button onClick={onClose}>Close</button></div>
      </div>
    </div>
  );
}
