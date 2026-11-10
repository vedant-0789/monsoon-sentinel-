"use client";

import type { Alert } from "@/lib/types";
import { ALERT_HEX } from "@/lib/colors";

export const ALERT_STYLE: Record<Alert, { bg: string; text: string; ring: string; soft: string }> = {
  green: { bg: "bg-[#1a9850]", text: "text-white", ring: "ring-[#1a9850]/30", soft: "bg-[#1a9850]/10" },
  yellow: { bg: "bg-[#f2c12e]", text: "text-zinc-900", ring: "ring-[#f2c12e]/40", soft: "bg-[#f2c12e]/15" },
  orange: { bg: "bg-[#f46d43]", text: "text-white", ring: "ring-[#f46d43]/30", soft: "bg-[#f46d43]/12" },
  red: { bg: "bg-[#c81e1e]", text: "text-white", ring: "ring-[#c81e1e]/30", soft: "bg-[#c81e1e]/10" },
};

/** Shape + colour so the alert level is readable without colour vision. */
export function AlertIcon({ alert, className = "h-6 w-6" }: { alert: Alert; className?: string }) {
  const c = "currentColor";
  if (alert === "green")
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden>
        <circle cx="12" cy="12" r="10" fill="none" stroke={c} strokeWidth="2" />
        <path d="M7.5 12.5l3 3 6-6.5" fill="none" stroke={c} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  if (alert === "yellow")
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden>
        <circle cx="12" cy="12" r="10" fill="none" stroke={c} strokeWidth="2" />
        <path d="M12 7v6" stroke={c} strokeWidth="2.2" strokeLinecap="round" />
        <circle cx="12" cy="16.5" r="1.3" fill={c} />
      </svg>
    );
  if (alert === "orange")
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden>
        <path d="M12 3l9.5 17h-19z" fill="none" stroke={c} strokeWidth="2" strokeLinejoin="round" />
        <path d="M12 9.5v5" stroke={c} strokeWidth="2.2" strokeLinecap="round" />
        <circle cx="12" cy="17.3" r="1.2" fill={c} />
      </svg>
    );
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden>
      <path d="M8 2.5h8L21.5 8v8L16 21.5H8L2.5 16V8z" fill="none" stroke={c} strokeWidth="2" strokeLinejoin="round" />
      <path d="M12 7.5v6" stroke={c} strokeWidth="2.2" strokeLinecap="round" />
      <circle cx="12" cy="16.6" r="1.2" fill={c} />
    </svg>
  );
}

export function AlertPill({ alert, label }: { alert: Alert; label: string }) {
  const s = ALERT_STYLE[alert];
  return (
    <span className={`inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-semibold ${s.bg} ${s.text}`}>
      <AlertIcon alert={alert} className="h-3.5 w-3.5" />
      {label}
    </span>
  );
}

export function Gauge({ value, alert, size = 88 }: { value: number; alert: Alert; size?: number }) {
  const r = 34;
  const circ = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(1, value));
  return (
    <svg width={size} height={size} viewBox="0 0 80 80" role="img" aria-label={`${Math.round(pct * 100)} percent`}>
      <circle cx="40" cy="40" r={r} fill="none" stroke="currentColor" strokeOpacity="0.12" strokeWidth="8" />
      <circle
        cx="40" cy="40" r={r} fill="none" stroke={ALERT_HEX[alert]} strokeWidth="8" strokeLinecap="round"
        strokeDasharray={`${circ * pct} ${circ}`} transform="rotate(-90 40 40)"
        style={{ transition: "stroke-dasharray 600ms ease" }}
      />
      <text x="40" y="45" textAnchor="middle" className="fill-current" fontSize="18" fontWeight="700">
        {Math.round(pct * 100)}%
      </text>
    </svg>
  );
}

export function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-zinc-100/80 px-3 py-2 dark:bg-zinc-800/60">
      <div className="text-[11px] leading-tight text-zinc-500 dark:text-zinc-400">{label}</div>
      <div className="mt-0.5 text-sm font-semibold tabular-nums">{value}</div>
    </div>
  );
}

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <section className={`rounded-2xl border border-zinc-200/80 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900 ${className}`}>
      {children}
    </section>
  );
}

export function Legend({ title, labels }: { title: string; labels: Record<Alert, string> }) {
  return (
    <div className="rounded-xl bg-white/95 px-3 py-2 text-xs shadow-md backdrop-blur dark:bg-zinc-900/95">
      <div className="mb-1 font-semibold">{title}</div>
      <div className="flex flex-wrap gap-x-3 gap-y-1">
        {(["green", "yellow", "orange", "red"] as Alert[]).map((a) => (
          <span key={a} className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: ALERT_HEX[a] }} />
            {labels[a]}
          </span>
        ))}
      </div>
    </div>
  );
}

export function Spinner({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" aria-hidden>
      <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeOpacity="0.2" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}
