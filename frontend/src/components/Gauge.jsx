import { useEffect, useState } from "react";
import { STATUS } from "../theme.js";

// ECAM-style engine dial for Remaining Useful Life.
// 240° sweep from 0 (left) to MAX cycles (right); red / amber arcs mark the
// critical and warning zones, the cyan band is the 90% interval, the needle the estimate.
const MAX = 125;
const START = 150; // degrees, SVG convention (0 = 3 o'clock, clockwise)
const SWEEP = 240;
const R = 100;

const ang = (v) => START + (Math.min(Math.max(v, 0), MAX) / MAX) * SWEEP;
const pt = (a, r = R) => [120 + r * Math.cos((a * Math.PI) / 180), 120 + r * Math.sin((a * Math.PI) / 180)];
function arc(v0, v1, r = R) {
  const [a0, a1] = [ang(v0), ang(v1)];
  const [x0, y0] = pt(a0, r);
  const [x1, y1] = pt(a1, r);
  return `M ${x0} ${y0} A ${r} ${r} 0 ${a1 - a0 > 180 ? 1 : 0} 1 ${x1} ${y1}`;
}

export default function Gauge({ mean, lower, upper, critical = 20, warning = 50, status = "HEALTHY" }) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    const id = requestAnimationFrame(() => setShown(mean));
    return () => cancelAnimationFrame(id);
  }, [mean]);
  const ticks = [0, 25, 50, 75, 100, 125];
  const capped = mean >= MAX;
  return (
    <svg viewBox="-18 -10 276 215" width="100%" style={{ maxWidth: 330 }} role="img"
         aria-label={`Predicted remaining useful life ${Math.round(mean)} cycles, 90% interval ${Math.round(lower)} to ${Math.round(upper)}`}>
      <path d={arc(0, MAX)} fill="none" stroke="#22323f" strokeWidth="10" />
      <path d={arc(0, critical)} fill="none" stroke={STATUS.CRITICAL.color} strokeWidth="10" />
      <path d={arc(critical, warning)} fill="none" stroke={STATUS.WARNING.color} strokeWidth="10" />
      <path d={arc(lower, Math.max(upper, lower + 0.5), R - 16)} fill="none" stroke="#1b98b8" strokeOpacity="0.55" strokeWidth="12" strokeLinecap="round" />
      {ticks.map((t) => {
        const [x0, y0] = pt(ang(t), R + 6);
        const [x1, y1] = pt(ang(t), R + 12);
        const [tx, ty] = pt(ang(t), R + 24);
        return (
          <g key={t}>
            <line x1={x0} y1={y0} x2={x1} y2={y1} stroke="#7b8d9b" strokeWidth="1.5" />
            <text x={tx} y={ty + 4} fontSize="10" fill="#7b8d9b" textAnchor="middle" fontFamily="B612, sans-serif">{t}</text>
          </g>
        );
      })}
      <g className="gauge-needle" style={{ transform: `rotate(${ang(shown)}deg)`, transformOrigin: "120px 120px" }}>
        <line x1="120" y1="120" x2={120 + R - 4} y2="120" stroke="#e8eef3" strokeWidth="3" strokeLinecap="round" />
      </g>
      <circle cx="120" cy="120" r="6" fill="#0b141c" stroke="#e8eef3" strokeWidth="2" />
      <text x="120" y="168" textAnchor="middle" fontFamily="B612, sans-serif" fontSize="38" fontWeight="700"
            fill={STATUS[status]?.color || "#e8eef3"}>{capped ? "125+" : Math.round(mean)}</text>
      <text x="120" y="188" textAnchor="middle" fontSize="11" fill="#a9b8c4" fontFamily="B612, sans-serif">
        cycles remaining · {Math.round(lower)}–{Math.round(upper)}
      </text>
    </svg>
  );
}
