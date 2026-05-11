import { useEffect, useState } from "react";
import type { Project } from "../types";
import { api } from "../api";

type Overlay = "none" | "star_mask" | "starless" | "background_model";

interface Props {
  project: Project | null;
  previewVersion: number;
  step: string;
  overlay: Overlay;
  onOverlayChange: (o: Overlay) => void;
}

export function ImageViewer({ project, previewVersion, step, overlay, onOverlayChange }: Props) {
  const [originalOk, setOriginalOk] = useState(false);
  const [currentOk, setCurrentOk] = useState(false);
  const [splitMode, setSplitMode] = useState<"side" | "split">("side");
  const [splitPos, setSplitPos] = useState(50);

  useEffect(() => {
    setOriginalOk(false);
    setCurrentOk(false);
  }, [project?.project_id, previewVersion]);

  if (!project) {
    return (
      <div className="empty-state" style={{ flex: 1 }}>
        <div style={{ fontSize: 18 }}>Easy Astro Photos</div>
        <div>Create or open a project to start stacking your astro frames.</div>
      </div>
    );
  }

  const v = previewVersion;
  const originalUrl = api.originalPreviewUrl(project.project_id, v);
  const currentUrl = api.currentPreviewUrl(project.project_id, v);
  const overlayUrl =
    overlay === "star_mask" ? api.starMaskUrl(project.project_id, v) :
    overlay === "starless" ? api.starlessUrl(project.project_id, v) :
    overlay === "background_model" ? api.backgroundModelUrl(project.project_id, v) :
    null;

  return (
    <>
      <div className="viewer-toolbar">
        <span className="muted">Step:</span>
        <span style={{ textTransform: "capitalize" }}>{step}</span>
        <div style={{ flex: 1 }} />
        <select value={splitMode} onChange={(e) => setSplitMode(e.target.value as "side" | "split")}>
          <option value="side">Side-by-side</option>
          <option value="split">Split slider</option>
        </select>
        <select value={overlay} onChange={(e) => onOverlayChange(e.target.value as Overlay)}>
          <option value="none">No overlay</option>
          <option value="star_mask">Star mask</option>
          <option value="starless">Starless</option>
          <option value="background_model">Background model</option>
        </select>
        <span className="muted">
          {project.has_stack ? "Stacked" : "Not stacked"} · {project.has_preview ? "Preview ready" : "No preview"}
        </span>
      </div>

      {splitMode === "side" ? (
        <div className="viewer-body">
          <div className="pane">
            <div className="pane-label">Original (reference frame)</div>
            <div className="pane-image-wrap">
              {originalOk ? (
                <img src={originalUrl} alt="Original reference frame" />
              ) : (
                <div className="pane-empty">
                  {project.has_stack ? "Loading reference..." : "Stack frames to see the reference frame here."}
                  <img src={originalUrl} alt="" style={{ display: "none" }} onLoad={() => setOriginalOk(true)} onError={() => setOriginalOk(false)} />
                </div>
              )}
            </div>
          </div>
          <div className="pane">
            <div className="pane-label">
              Processed preview {overlay !== "none" && <span className="muted">· overlay: {overlay}</span>}
            </div>
            <div className="pane-image-wrap" style={{ position: "relative" }}>
              {currentOk ? (
                <img src={currentUrl} alt="Processed preview" />
              ) : (
                <div className="pane-empty">
                  {project.has_preview ? "Loading preview..." : "Stack and stretch to see processed result."}
                  <img src={currentUrl} alt="" style={{ display: "none" }} onLoad={() => setCurrentOk(true)} onError={() => setCurrentOk(false)} />
                </div>
              )}
              {overlayUrl && currentOk && (
                <img
                  src={overlayUrl}
                  alt="overlay"
                  style={{
                    position: "absolute", inset: 0, width: "100%", height: "100%",
                    objectFit: "contain", opacity: 0.5, pointerEvents: "none",
                    mixBlendMode: "screen"
                  }}
                />
              )}
            </div>
          </div>
        </div>
      ) : (
        <div className="viewer-body">
          <div className="pane" style={{ position: "relative" }}>
            <div className="pane-label">Split slider — original ⇄ processed</div>
            <div className="pane-image-wrap" style={{ position: "relative" }}>
              <img
                src={originalUrl}
                alt="Original"
                onLoad={() => setOriginalOk(true)}
                style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "contain" }}
              />
              <div
                style={{
                  position: "absolute", top: 0, bottom: 0, left: 0,
                  width: `${splitPos}%`, overflow: "hidden",
                  borderRight: "1px solid var(--accent)"
                }}
              >
                <img
                  src={currentUrl}
                  alt="Processed"
                  onLoad={() => setCurrentOk(true)}
                  style={{
                    position: "absolute", left: 0, top: 0,
                    width: `${100 / (splitPos / 100)}%`, height: "100%",
                    objectFit: "contain", maxWidth: "none"
                  }}
                />
              </div>
              <input
                type="range"
                min={0}
                max={100}
                value={splitPos}
                onChange={(e) => setSplitPos(Number(e.target.value))}
                style={{
                  position: "absolute", left: 0, right: 0, bottom: 12,
                  margin: "0 auto", width: "60%"
                }}
              />
            </div>
          </div>
        </div>
      )}
    </>
  );
}
