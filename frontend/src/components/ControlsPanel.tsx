import { useState } from "react";
import type { Step } from "../App";
import type { Project } from "../types";
import { api } from "../api";

interface Props {
  project: Project;
  step: Step;
  busy: boolean;
  setBusy: (b: boolean) => void;
  advanced: boolean;
  onChanged: () => void;
  notify: (msg: string, kind?: "success" | "error") => void;
  onAdvance: (next: Step) => void;
  setOverlay: (o: "none" | "star_mask" | "starless" | "background_model") => void;
}

export function ControlsPanel(props: Props) {
  const { step } = props;
  if (step === "stack" || step === "align" || step === "calibrate") return <StackPanel {...props} />;
  if (step === "background") return <BackgroundPanel {...props} />;
  if (step === "denoise") return <DenoisePanel {...props} />;
  if (step === "deconvolution") return <SharpenPanel {...props} />;
  if (step === "stretch") return <StretchPanel {...props} />;
  if (step === "color") return <ColorPanel {...props} />;
  if (step === "stars") return <StarsPanel {...props} />;
  if (step === "pixel_math") return <PixelMathPanel {...props} />;
  if (step === "export") return <ExportPanel {...props} />;
  return null;
}

function Spinner({ children, busy }: { children: React.ReactNode; busy: boolean }) {
  return busy ? <><span className="spinner" /> {children}</> : <>{children}</>;
}

// --------------------------------------------------------------------------- //
function StackPanel({ project, busy, setBusy, advanced, onChanged, notify, onAdvance }: Props) {
  const [method, setMethod] = useState<
    "average" | "median" | "weighted_average" | "sigma_clip" | "winsorized_sigma_clip" | "minmax_reject"
  >("average");
  const [weighting, setWeighting] = useState<"equal" | "quality" | "stars" | "noise">("equal");
  const [sigmaLow, setSigmaLow] = useState(3.0);
  const [sigmaHigh, setSigmaHigh] = useState(3.0);
  const [calibrate, setCalibrate] = useState(false);
  const [useDarks, setUseDarks] = useState(true);
  const [useFlats, setUseFlats] = useState(true);
  const [useBias, setUseBias] = useState(true);
  const [cosmetic, setCosmetic] = useState(true);

  async function run() {
    setBusy(true);
    try {
      const result = await api.stack(project.project_id, {
        method,
        align: true,
        weighting,
        sigma_low: sigmaLow,
        sigma_high: sigmaHigh,
        calibrate,
        calibration: {
          use_darks: useDarks, use_flats: useFlats, use_bias: useBias,
          cosmetic_correction: cosmetic, dark_optimization: false,
          flat_normalization: "mean", master_method: "median"
        }
      });
      const d = result.details as Record<string, unknown>;
      notify(`Stacked ${d.stacked_frames ?? "?"} frames` + (Number(d.rejected_frames) > 0 ? ` (${d.rejected_frames} rejected)` : ""));
      onChanged();
      onAdvance("stretch");
    } catch (e) {
      notify(`Stack failed: ${(e as Error).message}`, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="group">
      <h2>Stack</h2>
      <p className="muted" style={{ margin: 0 }}>
        Aligns each light frame against the highest-quality reference, then integrates.
      </p>
      {!advanced ? (
        <select value={method} onChange={(e) => setMethod(e.target.value as typeof method)}>
          <option value="average">Standard Stack (average)</option>
          <option value="median">Best Quality Stack (median)</option>
          <option value="sigma_clip">Sigma-clipped Stack</option>
        </select>
      ) : (
        <>
          <div className="row between"><label>Method</label>
            <select value={method} onChange={(e) => setMethod(e.target.value as typeof method)}>
              <option value="average">Average</option>
              <option value="median">Median</option>
              <option value="weighted_average">Weighted average</option>
              <option value="sigma_clip">Sigma clip</option>
              <option value="winsorized_sigma_clip">Winsorized sigma clip</option>
              <option value="minmax_reject">Min/max reject</option>
            </select>
          </div>
          <div className="row between"><label>Weighting</label>
            <select value={weighting} onChange={(e) => setWeighting(e.target.value as typeof weighting)}>
              <option value="equal">Equal</option>
              <option value="quality">Quality score</option>
              <option value="stars">Star count</option>
              <option value="noise">Noise (lower=better)</option>
            </select>
          </div>
          {(method === "sigma_clip" || method === "winsorized_sigma_clip") && (
            <>
              <div className="row between"><label>Sigma low</label><span className="muted">{sigmaLow.toFixed(1)}</span></div>
              <input type="range" min={1} max={5} step={0.1} value={sigmaLow} onChange={(e) => setSigmaLow(+e.target.value)} />
              <div className="row between"><label>Sigma high</label><span className="muted">{sigmaHigh.toFixed(1)}</span></div>
              <input type="range" min={1} max={5} step={0.1} value={sigmaHigh} onChange={(e) => setSigmaHigh(+e.target.value)} />
            </>
          )}
        </>
      )}
      <div className="row" style={{ flexWrap: "wrap", gap: 12 }}>
        <label className="row" style={{ gap: 6 }}>
          <input type="checkbox" checked={calibrate} onChange={(e) => setCalibrate(e.target.checked)} />
          <span>Calibrate (Phase 2)</span>
        </label>
      </div>
      {calibrate && (
        <div className="group" style={{ background: "var(--bg-2)" }}>
          <p className="muted" style={{ margin: 0 }}>
            Calibration uses your imported darks, flats, and bias frames.
          </p>
          <label className="row" style={{ gap: 6 }}><input type="checkbox" checked={useDarks} onChange={(e) => setUseDarks(e.target.checked)} />Use darks</label>
          <label className="row" style={{ gap: 6 }}><input type="checkbox" checked={useFlats} onChange={(e) => setUseFlats(e.target.checked)} />Use flats</label>
          <label className="row" style={{ gap: 6 }}><input type="checkbox" checked={useBias} onChange={(e) => setUseBias(e.target.checked)} />Use bias / flat-darks</label>
          <label className="row" style={{ gap: 6 }}><input type="checkbox" checked={cosmetic} onChange={(e) => setCosmetic(e.target.checked)} />Cosmetic correction (hot pixels)</label>
        </div>
      )}
      <button className="primary" onClick={run} disabled={busy}>
        <Spinner busy={busy}>{busy ? "Stacking…" : "Stack Images"}</Spinner>
      </button>
    </div>
  );
}

// --------------------------------------------------------------------------- //
function StretchPanel({ project, busy, setBusy, advanced, onChanged, notify, onAdvance }: Props) {
  const [method, setMethod] = useState<"asinh" | "percentile" | "histogram" | "ghs">("asinh");
  const [bp, setBp] = useState(0.001);
  const [mid, setMid] = useState(0.25);
  const [wp, setWp] = useState(1.0);
  const [stretchFactor, setStretchFactor] = useState(4.0);
  const [protectHi, setProtectHi] = useState(true);
  const [preset, setPreset] = useState<string>("custom");

  function applyPreset(name: string) {
    setPreset(name);
    if (name === "auto") { setMethod("asinh"); setBp(0.001); setMid(0.25); }
    if (name === "gentle_nebula") { setMethod("asinh"); setBp(0.002); setMid(0.4); }
    if (name === "galaxy_core") { setMethod("histogram"); setBp(0.005); setMid(0.4); setWp(0.95); setProtectHi(true); }
    if (name === "cluster_natural") { setMethod("percentile"); }
    if (name === "milky_way") { setMethod("ghs"); setStretchFactor(2.5); }
  }

  async function run() {
    setBusy(true);
    try {
      await api.stretch(project.project_id, {
        method,
        black_point: bp,
        midtone: mid,
        white_point: wp,
        protect_highlights: protectHi,
        stretch_factor: stretchFactor,
        local_intensity: 0.5
      });
      notify("Stretch applied");
      onChanged();
    } catch (e) {
      notify(`Stretch failed: ${(e as Error).message}`, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="group">
        <h2>Stretch</h2>
        <p className="muted" style={{ margin: 0 }}>
          Linear stacked images look very dark. Stretching reveals faint detail.
          Always non-destructive — replays from the master stack.
        </p>
        <div className="row between"><label>Preset</label>
          <select value={preset} onChange={(e) => applyPreset(e.target.value)}>
            <option value="custom">Custom</option>
            <option value="auto">Auto Stretch</option>
            <option value="gentle_nebula">Gentle Nebula</option>
            <option value="galaxy_core">Galaxy Core Protection</option>
            <option value="cluster_natural">Star Cluster Natural</option>
            <option value="milky_way">Milky Way Widefield</option>
          </select>
        </div>
        {advanced && (
          <div className="row between"><label>Method</label>
            <select value={method} onChange={(e) => setMethod(e.target.value as typeof method)}>
              <option value="asinh">Asinh</option>
              <option value="percentile">Percentile</option>
              <option value="histogram">Histogram (MTF)</option>
              <option value="ghs">Generalized hyperbolic</option>
            </select>
          </div>
        )}
        <div className="row between"><label>Black point</label><span className="muted">{bp.toFixed(3)}</span></div>
        <input type="range" min={0} max={0.05} step={0.001} value={bp} onChange={(e) => setBp(+e.target.value)} />
        <div className="row between"><label>Midtone</label><span className="muted">{mid.toFixed(2)}</span></div>
        <input type="range" min={0.05} max={0.6} step={0.01} value={mid} onChange={(e) => setMid(+e.target.value)} />
        {advanced && (
          <>
            <div className="row between"><label>White point</label><span className="muted">{wp.toFixed(2)}</span></div>
            <input type="range" min={0.5} max={1.0} step={0.01} value={wp} onChange={(e) => setWp(+e.target.value)} />
            {method === "ghs" && (
              <>
                <div className="row between"><label>Stretch factor</label><span className="muted">{stretchFactor.toFixed(1)}</span></div>
                <input type="range" min={0.5} max={10} step={0.1} value={stretchFactor} onChange={(e) => setStretchFactor(+e.target.value)} />
              </>
            )}
            <label className="row" style={{ gap: 6 }}>
              <input type="checkbox" checked={protectHi} onChange={(e) => setProtectHi(e.target.checked)} />
              <span>Protect highlights</span>
            </label>
          </>
        )}
        <button className="primary" onClick={run} disabled={busy}>
          <Spinner busy={busy}>{busy ? "Stretching…" : "Apply Stretch"}</Spinner>
        </button>
      </div>
      <div className="group">
        <button onClick={() => onAdvance("color")}>Next: Color →</button>
      </div>
    </>
  );
}

// --------------------------------------------------------------------------- //
function BackgroundPanel({ project, busy, setBusy, advanced, onChanged, notify, setOverlay }: Props) {
  const [method, setMethod] = useState<"polynomial" | "rbf" | "ai">("polynomial");
  const [strength, setStrength] = useState(1.0);
  const [smoothing, setSmoothing] = useState(0.5);
  const [degree, setDegree] = useState(3);
  const [correction, setCorrection] = useState<"subtraction" | "division">("subtraction");
  const [protectObjects, setProtectObjects] = useState(true);

  async function run() {
    setBusy(true);
    try {
      await api.background(project.project_id, {
        method, strength, smoothing, degree, correction, protect_objects: protectObjects, samples: 32
      });
      notify("Light pollution / gradient removed");
      setOverlay("background_model");
      onChanged();
    } catch (e) {
      notify(`Background extraction failed: ${(e as Error).message}`, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="group">
      <h2>Background / Gradient</h2>
      <p className="muted" style={{ margin: 0 }}>Removes light pollution gradients and color casts.</p>
      <div className="row between"><label>Strength</label><span className="muted">{Math.round(strength * 100)}%</span></div>
      <input type="range" min={0} max={1} step={0.01} value={strength} onChange={(e) => setStrength(+e.target.value)} />
      <div className="row between"><label>Smoothing</label><span className="muted">{Math.round(smoothing * 100)}%</span></div>
      <input type="range" min={0} max={1} step={0.01} value={smoothing} onChange={(e) => setSmoothing(+e.target.value)} />
      <label className="row" style={{ gap: 6 }}>
        <input type="checkbox" checked={protectObjects} onChange={(e) => setProtectObjects(e.target.checked)} />
        <span>Protect nebula / galaxy</span>
      </label>
      {advanced && (
        <>
          <div className="row between"><label>Method</label>
            <select value={method} onChange={(e) => setMethod(e.target.value as typeof method)}>
              <option value="polynomial">Polynomial surface</option>
              <option value="rbf">RBF / spline</option>
              <option value="ai">AI model (if installed)</option>
            </select>
          </div>
          <div className="row between"><label>Polynomial degree</label>
            <input type="number" min={1} max={5} value={degree} onChange={(e) => setDegree(+e.target.value)} style={{ width: 64 }} />
          </div>
          <div className="row between"><label>Correction</label>
            <select value={correction} onChange={(e) => setCorrection(e.target.value as typeof correction)}>
              <option value="subtraction">Subtract</option>
              <option value="division">Divide</option>
            </select>
          </div>
        </>
      )}
      <button className="primary" onClick={run} disabled={busy}>
        <Spinner busy={busy}>{busy ? "Working…" : "Remove Light Pollution / Gradient"}</Spinner>
      </button>
    </div>
  );
}

// --------------------------------------------------------------------------- //
function DenoisePanel({ project, busy, setBusy, advanced, onChanged, notify }: Props) {
  const [method, setMethod] = useState<"nlm" | "wavelet" | "starlet" | "bilateral" | "ai">("starlet");
  const [strength, setStrength] = useState(0.45);
  const [protectStars, setProtectStars] = useState(true);
  const [scales, setScales] = useState(5);
  const [model, setModel] = useState("");

  async function run(preset?: number) {
    const s = preset ?? strength;
    setBusy(true);
    try {
      await api.denoise(project.project_id, { method, strength: s, protect_stars: protectStars, scales, model_name: model || undefined });
      notify("Denoise applied");
      onChanged();
    } catch (e) {
      notify(`Denoise failed: ${(e as Error).message}`, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="group">
      <h2>Denoise</h2>
      <p className="muted" style={{ margin: 0 }}>Best done before aggressive stretching, but works at any stage.</p>
      <div className="row" style={{ gap: 6 }}>
        <button onClick={() => run(0.2)} disabled={busy}>Light</button>
        <button onClick={() => run(0.45)} disabled={busy}>Balanced</button>
        <button onClick={() => run(0.8)} disabled={busy}>Strong</button>
      </div>
      <div className="row between"><label>Strength</label><span className="muted">{Math.round(strength * 100)}%</span></div>
      <input type="range" min={0} max={1} step={0.01} value={strength} onChange={(e) => setStrength(+e.target.value)} />
      <label className="row" style={{ gap: 6 }}>
        <input type="checkbox" checked={protectStars} onChange={(e) => setProtectStars(e.target.checked)} />
        <span>Protect stars</span>
      </label>
      {advanced && (
        <>
          <div className="row between"><label>Algorithm</label>
            <select value={method} onChange={(e) => setMethod(e.target.value as typeof method)}>
              <option value="starlet">Starlet (multiscale, astro-tuned)</option>
              <option value="nlm">Non-local means</option>
              <option value="wavelet">Wavelet (alias of starlet)</option>
              <option value="bilateral">Bilateral</option>
              <option value="ai">AI / ONNX</option>
            </select>
          </div>
          {(method === "starlet" || method === "wavelet") && (
            <>
              <div className="row between"><label>Scales</label><span className="muted">{scales}</span></div>
              <input type="range" min={3} max={7} step={1} value={scales} onChange={(e) => setScales(+e.target.value)} />
            </>
          )}
          {method === "ai" && (
            <input placeholder="ONNX model name (optional)" value={model} onChange={(e) => setModel(e.target.value)} />
          )}
        </>
      )}
      <button className="primary" onClick={() => run()} disabled={busy}>
        <Spinner busy={busy}>{busy ? "Denoising…" : "Apply Denoise"}</Spinner>
      </button>
    </div>
  );
}

// --------------------------------------------------------------------------- //
function SharpenPanel({ project, busy, setBusy, advanced, onChanged, notify }: Props) {
  const [method, setMethod] = useState<"richardson_lucy" | "wiener" | "unsharp" | "ai">("richardson_lucy");
  const [strength, setStrength] = useState(0.5);
  const [fwhm, setFwhm] = useState(0.0); // 0 = auto-estimate from stars
  const [iters, setIters] = useState(20);
  const [starMode, setStarMode] = useState(false);

  async function run(preset?: { strength?: number; fwhm?: number; method?: typeof method; starMode?: boolean }) {
    setBusy(true);
    try {
      await api.deconvolve(project.project_id, {
        method: preset?.method ?? method,
        strength: preset?.strength ?? strength,
        fwhm: preset?.fwhm ?? fwhm,
        iterations: iters,
        star_mode: preset?.starMode ?? starMode,
        protect_ringing: true
      });
      notify("Sharpen applied");
      onChanged();
    } catch (e) {
      notify(`Sharpen failed: ${(e as Error).message}`, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="group">
      <h2>Sharpen / Deconvolution</h2>
      <p className="muted" style={{ margin: 0 }}>Recovers detail blurred by seeing and optics.</p>
      <div className="row" style={{ flexWrap: "wrap", gap: 6 }}>
        <button onClick={() => run({ strength: 0.3, method: "unsharp" })} disabled={busy}>Gentle</button>
        <button onClick={() => run({ strength: 0.6, fwhm: 0, method: "richardson_lucy" })} disabled={busy}>Nebula</button>
        <button onClick={() => run({ strength: 0.5, fwhm: 0, method: "richardson_lucy" })} disabled={busy}>Galaxy</button>
        <button onClick={() => run({ strength: 0.7, fwhm: 0, starMode: true, method: "richardson_lucy" })} disabled={busy}>Star Tightening</button>
      </div>
      <div className="row between"><label>Strength</label><span className="muted">{Math.round(strength * 100)}%</span></div>
      <input type="range" min={0} max={1} step={0.01} value={strength} onChange={(e) => setStrength(+e.target.value)} />
      <div className="row between"><label>Star FWHM (px, 0 = auto)</label><span className="muted">{fwhm === 0 ? "auto" : fwhm.toFixed(1)}</span></div>
      <input type="range" min={0} max={8} step={0.1} value={fwhm} onChange={(e) => setFwhm(+e.target.value)} />
      {advanced && (
        <>
          <div className="row between"><label>Method</label>
            <select value={method} onChange={(e) => setMethod(e.target.value as typeof method)}>
              <option value="richardson_lucy">Richardson-Lucy</option>
              <option value="wiener">Wiener</option>
              <option value="unsharp">Unsharp mask</option>
              <option value="ai">AI / ONNX</option>
            </select>
          </div>
          <div className="row between"><label>Iterations</label>
            <input type="number" min={1} max={50} value={iters} onChange={(e) => setIters(+e.target.value)} style={{ width: 64 }} />
          </div>
          <label className="row" style={{ gap: 6 }}>
            <input type="checkbox" checked={starMode} onChange={(e) => setStarMode(e.target.checked)} />
            <span>Star tightening mode</span>
          </label>
        </>
      )}
      <button className="primary" onClick={() => run()} disabled={busy}>
        <Spinner busy={busy}>{busy ? "Sharpening…" : "Apply Sharpen"}</Spinner>
      </button>
    </div>
  );
}

// --------------------------------------------------------------------------- //
function ColorPanel({ project, busy, setBusy, advanced, onChanged, notify }: Props) {
  const [mode, setMode] = useState<"natural_rgb" | "sho" | "hoo" | "custom">("natural_rgb");
  const [saturation, setSaturation] = useState(0);
  const [greenReduction, setGreenReduction] = useState(0);
  const [bgNeutral, setBgNeutral] = useState(true);
  const [preserveStars, setPreserveStars] = useState(true);

  async function run(palette?: typeof mode, satOverride?: number, greenOverride?: number) {
    setBusy(true);
    try {
      await api.color(project.project_id, {
        mode: palette ?? mode,
        saturation: satOverride ?? saturation,
        green_reduction: greenOverride ?? greenReduction,
        background_neutralization: bgNeutral,
        preserve_star_color: preserveStars,
        channel_map: {}
      });
      notify("Color applied");
      onChanged();
    } catch (e) {
      notify(`Color failed: ${(e as Error).message}`, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="group">
      <h2>Color</h2>
      {mode !== "natural_rgb" && (
        <p className="muted" style={{ margin: 0, color: "var(--warn)" }}>
          Hubble/SHO and HOO are scientifically-inspired false color, not true natural color.
        </p>
      )}
      <div className="row between"><label>Mode</label>
        <select value={mode} onChange={(e) => setMode(e.target.value as typeof mode)}>
          <option value="natural_rgb">Natural RGB</option>
          <option value="sho">Hubble SHO (S→R, Hα→G, OIII→B)</option>
          <option value="hoo">HOO (Hα→R, OIII→G/B)</option>
          <option value="custom">Custom</option>
        </select>
      </div>
      <div className="row between"><label>Saturation</label><span className="muted">{saturation.toFixed(2)}</span></div>
      <input type="range" min={-1} max={1} step={0.05} value={saturation} onChange={(e) => setSaturation(+e.target.value)} />
      <div className="row between"><label>Green reduction (SCNR)</label><span className="muted">{Math.round(greenReduction * 100)}%</span></div>
      <input type="range" min={0} max={1} step={0.05} value={greenReduction} onChange={(e) => setGreenReduction(+e.target.value)} />
      <label className="row" style={{ gap: 6 }}>
        <input type="checkbox" checked={bgNeutral} onChange={(e) => setBgNeutral(e.target.checked)} />
        <span>Background neutralization</span>
      </label>
      {advanced && (
        <label className="row" style={{ gap: 6 }}>
          <input type="checkbox" checked={preserveStars} onChange={(e) => setPreserveStars(e.target.checked)} />
          <span>Preserve star color</span>
        </label>
      )}
      <div className="row" style={{ flexWrap: "wrap", gap: 6 }}>
        <button onClick={() => run("sho", 0.3, 0.7)} disabled={busy}>Classic Hubble</button>
        <button onClick={() => run("sho", 0.2, 0.95)} disabled={busy}>Hubble Natural</button>
        <button onClick={() => run("hoo", 0.3, 0)} disabled={busy}>HOO</button>
      </div>
      <button className="primary" onClick={() => run()} disabled={busy}>
        <Spinner busy={busy}>{busy ? "Working…" : "Apply Color"}</Spinner>
      </button>
    </div>
  );
}

// --------------------------------------------------------------------------- //
function StarsPanel({ project, busy, setBusy, onChanged, notify, setOverlay }: Props) {
  const [amount, setAmount] = useState(0.5);

  async function reduce() {
    setBusy(true);
    try {
      await api.starReduction(project.project_id, amount);
      notify("Stars reduced");
      onChanged();
    } catch (e) { notify(`Failed: ${(e as Error).message}`, "error"); } finally { setBusy(false); }
  }
  async function mask() {
    setBusy(true);
    try { await api.starMask(project.project_id); setOverlay("star_mask"); onChanged(); notify("Star mask generated"); }
    catch (e) { notify(`Failed: ${(e as Error).message}`, "error"); } finally { setBusy(false); }
  }
  async function starless() {
    setBusy(true);
    try { await api.starless(project.project_id); setOverlay("starless"); onChanged(); notify("Starless preview generated"); }
    catch (e) { notify(`Failed: ${(e as Error).message}`, "error"); } finally { setBusy(false); }
  }

  return (
    <div className="group">
      <h2>Star Processing</h2>
      <p className="muted" style={{ margin: 0 }}>Generate masks and reduce stars without damaging nebula/galaxy detail.</p>
      <button onClick={mask} disabled={busy}>Generate Star Mask (overlay)</button>
      <button onClick={starless} disabled={busy}>Generate Starless Preview (overlay)</button>
      <div className="row between"><label>Reduction amount</label><span className="muted">{Math.round(amount * 100)}%</span></div>
      <input type="range" min={0} max={1} step={0.05} value={amount} onChange={(e) => setAmount(+e.target.value)} />
      <button className="primary" onClick={reduce} disabled={busy}>
        <Spinner busy={busy}>{busy ? "Working…" : "Reduce Stars"}</Spinner>
      </button>
    </div>
  );
}

// --------------------------------------------------------------------------- //
function PixelMathPanel({ project, busy, setBusy, onChanged, notify }: Props) {
  const [expr, setExpr] = useState("clip(image * 1.1 - 0.02, 0, 1)");

  async function run() {
    setBusy(true);
    try {
      await api.pixelMath(project.project_id, expr, true);
      notify("Pixel math applied");
      onChanged();
    } catch (e) { notify(`Pixel math failed: ${(e as Error).message}`, "error"); } finally { setBusy(false); }
  }

  return (
    <div className="group">
      <h2>Pixel Math</h2>
      <p className="muted" style={{ margin: 0 }}>
        Variables: <code>image</code>, <code>r</code>, <code>g</code>, <code>b</code>.
        Functions: <code>min, max, clip, sqrt, log, exp, asinh, tanh, where</code>.
      </p>
      <textarea
        value={expr}
        onChange={(e) => setExpr(e.target.value)}
        rows={5}
        style={{ background: "var(--bg-2)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: 6, padding: 8, fontFamily: "monospace" }}
      />
      <button className="primary" onClick={run} disabled={busy}>
        <Spinner busy={busy}>{busy ? "Running…" : "Apply Expression"}</Spinner>
      </button>
    </div>
  );
}

// --------------------------------------------------------------------------- //
function ExportPanel({ project, busy, setBusy, notify, onChanged }: Props) {
  const [fmt, setFmt] = useState<"png" | "tif" | "fit" | "jpg">("png");

  async function run() {
    setBusy(true);
    try {
      await api.exportImage(project.project_id, fmt);
      notify("Export ready");
      window.open(api.exportFileUrl(project.project_id, fmt), "_blank");
      onChanged();
    } catch (e) { notify(`Export failed: ${(e as Error).message}`, "error"); } finally { setBusy(false); }
  }

  return (
    <div className="group">
      <h2>Export</h2>
      <p className="muted" style={{ margin: 0 }}>Original frames are never modified.</p>
      <div className="row between"><label>Format</label>
        <select value={fmt} onChange={(e) => setFmt(e.target.value as typeof fmt)}>
          <option value="png">PNG (8-bit)</option>
          <option value="jpg">JPEG</option>
          <option value="tif">TIFF (16-bit)</option>
          <option value="fit">FITS (32-bit float)</option>
        </select>
      </div>
      <button className="primary" onClick={run} disabled={busy}>
        <Spinner busy={busy}>{busy ? "Exporting…" : "Export"}</Spinner>
      </button>
    </div>
  );
}
