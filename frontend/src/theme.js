// Validated palette (dark mode steps) — see README "Design system".
export const C = {
  surface: "#1a1a19",
  surface2: "#232322",
  grid: "#2e2e2c",
  axis: "#55544f",
  text: "#f0efec",
  text2: "#c3c2b7",
  muted: "#8f8e86",
  series: ["#3987e5", "#d95926", "#199e70"], // blue, orange, aqua (all-pairs safe)
  pos: "#3987e5", // diverging: increases RUL
  neg: "#e66767", // diverging: decreases RUL
  mid: "#383835",
};

export const STATUS = {
  HEALTHY: { color: "#0ca30c", label: "Healthy", icon: "●" },
  WATCH: { color: "#fab219", label: "Watch", icon: "◐" },
  WARNING: { color: "#ec835a", label: "Warning", icon: "▲" },
  CRITICAL: { color: "#d03b3b", label: "Critical", icon: "■" },
};

export const baseLayout = (extra = {}) => ({
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  font: { family: "Inter, system-ui, -apple-system, Segoe UI, sans-serif", color: C.text2, size: 12 },
  margin: { l: 52, r: 16, t: 12, b: 40 },
  hoverlabel: { bgcolor: "#2b2b29", bordercolor: "#444", font: { color: C.text, size: 12 } },
  legend: { orientation: "h", y: 1.12, x: 0, font: { color: C.text2 } },
  xaxis: { gridcolor: C.grid, zeroline: false, linecolor: C.axis, tickcolor: C.axis, ...(extra.xaxis || {}) },
  yaxis: { gridcolor: C.grid, zeroline: false, linecolor: C.axis, tickcolor: C.axis, ...(extra.yaxis || {}) },
  ...Object.fromEntries(Object.entries(extra).filter(([k]) => !["xaxis", "yaxis"].includes(k))),
});

export const plotConfig = { displaylogo: false, responsive: true, modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d"] };
