// "Glass cockpit" theme, after Airbus ECAM conventions:
// green = normal, amber = caution, red = warning, cyan = interactive / model output,
// magenta = reference (targets, ground truth). Series pair validated for CVD (ΔE ≥ 8).
export const C = {
  bg: "#0b141c",
  surface: "#101b25",
  surface2: "#16242f",
  line: "#22323f",
  grid: "#1c2a36",
  axis: "#3b5061",
  text: "#e8eef3",
  text2: "#a9b8c4",
  muted: "#7b8d9b",
  cyan: "#1b98b8",
  cyanBright: "#4cc3df",
  magenta: "#d0598f",
  series: ["#1b98b8", "#d0598f", "#7f8f3a"],
  pos: "#1b98b8", // SHAP: raises RUL
  neg: "#f29a38", // SHAP: lowers RUL (caution)
  mid: "#1d2b37",
};

export const STATUS = {
  HEALTHY: { color: "#3fcf7a", label: "Healthy", icon: "●" },
  WATCH: { color: "#e3cf4f", label: "Watch", icon: "◆" },
  WARNING: { color: "#f29a38", label: "Warning", icon: "▲" },
  CRITICAL: { color: "#f0524d", label: "Critical", icon: "■" },
};

const FONT = "B612, system-ui, sans-serif";
export const MONO = FONT;

export const baseLayout = (extra = {}) => ({
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  font: { family: FONT, color: C.text2, size: 11 },
  margin: { l: 52, r: 16, t: 12, b: 40 },
  hoverlabel: { bgcolor: C.surface2, bordercolor: C.axis, font: { family: MONO, color: C.text, size: 12 } },
  legend: { orientation: "h", y: 1.12, x: 0, font: { color: C.text2 } },
  xaxis: { gridcolor: C.grid, zeroline: false, linecolor: C.axis, tickcolor: C.axis, tickfont: { family: MONO }, ...(extra.xaxis || {}) },
  yaxis: { gridcolor: C.grid, zeroline: false, linecolor: C.axis, tickcolor: C.axis, tickfont: { family: MONO }, ...(extra.yaxis || {}) },
  ...Object.fromEntries(Object.entries(extra).filter(([k]) => !["xaxis", "yaxis"].includes(k))),
});

export const plotConfig = { displaylogo: false, responsive: true, modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d"] };
