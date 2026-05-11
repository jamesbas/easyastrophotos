import type { Step } from "../App";

const STEPS: { id: Step; label: string }[] = [
  { id: "import", label: "Import" },
  { id: "calibrate", label: "Calibrate" },
  { id: "align", label: "Align" },
  { id: "stack", label: "Stack" },
  { id: "background", label: "Background" },
  { id: "denoise", label: "Denoise" },
  { id: "deconvolution", label: "Sharpen" },
  { id: "stretch", label: "Stretch" },
  { id: "color", label: "Color" },
  { id: "stars", label: "Stars" },
  { id: "pixel_math", label: "Pixel Math" },
  { id: "export", label: "Export" }
];

interface Props {
  step: Step;
  onSelect: (s: Step) => void;
  hasStack: boolean;
  hasPreview: boolean;
  hasProject: boolean;
}

export function WorkflowRail({ step, onSelect, hasStack, hasPreview, hasProject }: Props) {
  function isEnabled(id: Step): boolean {
    if (!hasProject) return id === "import";
    if (id === "import") return true;
    if (id === "calibrate" || id === "align" || id === "stack") return true;
    // Post-stack operations require a stack.
    return hasStack || id === "stack";
  }

  return (
    <nav className="rail">
      {STEPS.map((s, i) => {
        const enabled = isEnabled(s.id);
        const active = step === s.id;
        return (
          <div
            key={s.id}
            className={`rail-step${active ? " active" : ""}${enabled ? "" : " disabled"}`}
            onClick={() => enabled && onSelect(s.id)}
          >
            <span className="num">{i + 1}</span>
            <span>{s.label}</span>
          </div>
        );
      })}
    </nav>
  );
}
