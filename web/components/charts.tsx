"use client";

import { ALERT_HEX } from "@/lib/colors";
import type { HistoryPoint } from "@/lib/types";

/** Rain bars (observed / model) with the forecast heavy-rain chance as a line. */
export function Timeline({ data, height = 96, labels }: {
  data: HistoryPoint[];
  height?: number;
  labels: { rain: string; chance: string };
}) {
  if (!data.length) return null;
  const W = 300;
  const H = height;
  const pad = { l: 4, r: 4, t: 8, b: 16 };
  const iw = W - pad.l - pad.r;
  const ih = H - pad.t - pad.b;
  const maxRain = Math.max(64.5, ...data.map((d) => d.rain_mm));
  const bw = iw / data.length;
  const y = (mm: number) => pad.t + ih - (mm / maxRain) * ih;
  const yp = (p: number) => pad.t + ih - p * ih;
  const hasP = data.some((d) => d.probability !== null);
  const line = data
    .map((d, i) => (d.probability === null ? null : `${pad.l + bw * (i + 0.5)},${yp(d.probability)}`))
    .filter(Boolean)
    .join(" ");
  const heavy = y(64.5);
  return (
    <figure>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img"
        aria-label={`${labels.rain}: ${data.map((d) => `${d.date} ${d.rain_mm} mm`).join(", ")}`}>
        <line x1={pad.l} x2={W - pad.r} y1={heavy} y2={heavy} stroke="currentColor" strokeOpacity="0.25" strokeDasharray="3 3" />
        <text x={W - pad.r} y={heavy - 2} textAnchor="end" fontSize="8" className="fill-current opacity-50">64.5 mm</text>
        {data.map((d, i) => {
          const h = pad.t + ih - y(d.rain_mm);
          const c = d.rain_mm >= 64.5 ? ALERT_HEX.red : d.rain_mm >= 35 ? ALERT_HEX.orange : "#60a5fa";
          return (
            <g key={d.date}>
              <rect x={pad.l + bw * i + bw * 0.15} y={y(d.rain_mm)} width={bw * 0.7} height={Math.max(h, 0.5)} rx="1.5" fill={c} opacity="0.85">
                <title>{`${d.date}: ${d.rain_mm} mm${d.probability !== null ? ` · ${Math.round(d.probability * 100)}%` : ""}`}</title>
              </rect>
              {(i === 0 || i === data.length - 1) && (
                <text x={pad.l + bw * (i + 0.5)} y={H - 4} textAnchor={i === 0 ? "start" : "end"} fontSize="8" className="fill-current opacity-60">
                  {d.date.slice(5)}
                </text>
              )}
            </g>
          );
        })}
        {hasP && <polyline points={line} fill="none" stroke="#111827" strokeWidth="1.6" className="dark:stroke-white" />}
        {hasP && data.map((d, i) => d.probability !== null && (
          <circle key={d.date} cx={pad.l + bw * (i + 0.5)} cy={yp(d.probability)} r="1.8" className="fill-zinc-900 dark:fill-white" />
        ))}
      </svg>
      <figcaption className="mt-1 flex gap-3 text-[10px] text-zinc-500">
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm bg-blue-400" />{labels.rain}</span>
        {hasP && <span className="flex items-center gap-1"><span className="h-0.5 w-3 bg-zinc-900 dark:bg-white" />{labels.chance}</span>}
      </figcaption>
    </figure>
  );
}

/** Horizontal bar list for model benchmarks. */
export function Bars({ rows, max = 1, format = (v: number) => v.toFixed(3), highlight }: {
  rows: { label: string; value: number }[];
  max?: number;
  format?: (v: number) => string;
  highlight?: string;
}) {
  return (
    <ul className="space-y-1.5">
      {rows.map((r) => (
        <li key={r.label} className="text-xs">
          <div className="flex justify-between gap-2">
            <span className={r.label === highlight ? "font-semibold" : ""}>{r.label}</span>
            <span className="tabular-nums text-zinc-500">{format(r.value)}</span>
          </div>
          <div className="mt-0.5 h-1.5 rounded-full bg-zinc-100 dark:bg-zinc-800">
            <div
              className={`h-1.5 rounded-full ${r.label === highlight ? "bg-blue-600" : "bg-zinc-400 dark:bg-zinc-500"}`}
              style={{ width: `${Math.max(0, Math.min(1, r.value / max)) * 100}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}
