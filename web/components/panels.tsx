"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { ALERT_COPY, factor } from "@/lib/i18n";
import { useSentinel } from "@/lib/store";
import type { Alert } from "@/lib/types";
import { ALERT_STYLE, AlertIcon, AlertPill, Card, Gauge, Spinner, Stat } from "./ui";

const mm = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${v.toFixed(0)} mm`);

export function AlertHero() {
  const { bulletin: b, lang, t, loading, error, mode } = useSentinel();
  if (error)
    return (
      <Card>
        <p className="text-sm font-medium text-red-600">{t("apiDown")}</p>
        <p className="mt-1 text-xs text-zinc-500">{error}</p>
      </Card>
    );
  if (!b)
    return (
      <Card className="flex items-center gap-2 text-sm text-zinc-500">
        <Spinner /> {t("loading")}
      </Card>
    );
  const a = b.headline_alert;
  const s = ALERT_STYLE[a];
  const copy = ALERT_COPY[lang][a];
  const date = new Date(b.date + "T00:00:00").toLocaleDateString(lang === "en" ? "en-IN" : lang === "mr" ? "mr-IN" : "hi-IN", {
    weekday: "short", day: "numeric", month: "short", year: "numeric",
  });
  return (
    <div className={`overflow-hidden rounded-2xl shadow-sm ring-1 ${s.ring} ${loading ? "opacity-60" : ""} transition-opacity`}>
      <div className={`${s.bg} ${s.text} flex items-center gap-3 px-4 py-3`}>
        <AlertIcon alert={a} className="h-9 w-9 shrink-0" />
        <div className="min-w-0">
          <div className="text-xl font-bold leading-tight">{copy.title}</div>
          <div className="text-xs opacity-90">
            Pune · {date} · {mode === "live" ? `${t("issued")} ${b.issued_at}` : `${t("replay")}`}
          </div>
        </div>
      </div>
      <div className="space-y-3 bg-white p-4 dark:bg-zinc-900">
        <p className="text-[15px] leading-snug">{copy.advice}</p>
        {!b.in_season && (
          <p className="rounded-lg bg-sky-50 px-3 py-2 text-xs leading-snug text-sky-900 dark:bg-sky-950/50 dark:text-sky-200">
            {t("offSeason")}
          </p>
        )}
        <div className="flex items-center gap-4">
          <Gauge value={b.heavy_rain.probability} alert={a} />
          <div className="min-w-0 flex-1">
            <div className="text-xs text-zinc-500">{t("heavyRainChance")}</div>
            <div className="text-lg font-semibold capitalize">{t(b.heavy_rain.likelihood)}</div>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-2">
          {b.heavy_rain.observed_rain_mm !== null && <Stat label={t("observedRain")} value={mm(b.heavy_rain.observed_rain_mm)} />}
          {b.heavy_rain.nwp_rain_24h_mm !== null && <Stat label={t("forecastRain")} value={mm(b.heavy_rain.nwp_rain_24h_mm)} />}
          <Stat label={t("last3days")} value={mm(b.heavy_rain.rain_last_3_days_mm)} />
        </div>
        <Drivers />
      </div>
    </div>
  );
}

export function Drivers() {
  const { bulletin: b, lang, t } = useSentinel();
  const [open, setOpen] = useState(true);
  if (!b || !b.heavy_rain.drivers.length) return null;
  const max = Math.max(...b.heavy_rain.drivers.map((d) => d.strength));
  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800">
      <button onClick={() => setOpen(!open)} className="flex w-full items-center justify-between px-3 py-2 text-sm font-semibold" aria-expanded={open}>
        {t("why")}
        <svg viewBox="0 0 20 20" className={`h-4 w-4 transition ${open ? "rotate-180" : ""}`} aria-hidden>
          <path d="M5 8l5 5 5-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </button>
      {open && (
        <ul className="space-y-2 px-3 pb-3">
          {b.heavy_rain.drivers.map((d) => (
            <li key={d.factor} className="text-sm">
              <div className="flex items-center gap-2">
                <span className={`text-base font-bold ${d.effect === "raises" ? "text-red-600" : "text-emerald-600"}`} aria-hidden>
                  {d.effect === "raises" ? "↑" : "↓"}
                </span>
                <span className="flex-1 first-letter:uppercase">{factor(lang, d.factor)}</span>
                <span className="text-xs text-zinc-500">{t(d.effect)}</span>
              </div>
              <div className="ml-6 mt-1 h-1.5 rounded-full bg-zinc-100 dark:bg-zinc-800">
                <div
                  className={`h-1.5 rounded-full ${d.effect === "raises" ? "bg-red-500/80" : "bg-emerald-500/80"}`}
                  style={{ width: `${(d.strength / max) * 100}%` }}
                />
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function StreetCheck({ onLocate }: { onLocate: (lat: number, lon: number) => void }) {
  const { t, picked, lang, clearPick } = useSentinel();
  const [locating, setLocating] = useState(false);
  const [geoErr, setGeoErr] = useState<string | null>(null);
  const locate = () => {
    if (!navigator.geolocation) return setGeoErr("Geolocation not available");
    setLocating(true);
    setGeoErr(null);
    navigator.geolocation.getCurrentPosition(
      (p) => {
        setLocating(false);
        onLocate(p.coords.latitude, p.coords.longitude);
      },
      (e) => {
        setLocating(false);
        setGeoErr(e.message);
      },
      { enableHighAccuracy: true, timeout: 10000 },
    );
  };
  const info = picked?.info;
  const resultRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (picked) resultRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [picked]);
  return (
    <Card>
      <button
        onClick={locate}
        className="flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-3 text-[15px] font-semibold text-white shadow-sm transition hover:bg-blue-700 active:scale-[0.99]"
      >
        {locating ? <Spinner /> : (
          <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden>
            <circle cx="12" cy="12" r="3.5" fill="currentColor" />
            <path d="M12 2v3M12 19v3M2 12h3M19 12h3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            <circle cx="12" cy="12" r="7" fill="none" stroke="currentColor" strokeWidth="2" />
          </svg>
        )}
        {locating ? t("locating") : t("checkStreet")}
      </button>
      <p className="mt-2 text-center text-xs text-zinc-500">{t("tapMap")}</p>
      {geoErr && <p className="mt-2 text-xs text-red-600">{geoErr}</p>}
      {picked && (
        <div ref={resultRef} className="mt-3 scroll-mb-4 rounded-xl border border-zinc-200 p-3 dark:border-zinc-800" aria-live="polite">
          {picked.loading && <div className="flex items-center gap-2 text-sm text-zinc-500"><Spinner /> …</div>}
          {picked.error && <p className="text-sm text-red-600">{picked.error}</p>}
          {info && !info.covered && <p className="text-sm">{t("outside")}</p>}
          {info && info.covered && (
            <div className="space-y-2">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="text-xs text-zinc-500">{t("nearestRoad")}</div>
                  <div className="truncate font-semibold">
                    {info.nearest_road.startsWith("Near ") ? t("nearRoad", { r: info.nearest_road.slice(5) }) : info.nearest_road}
                  </div>
                </div>
                <AlertPill alert={info.alert} label={ALERT_COPY[lang][info.alert].title} />
              </div>
              <p className="text-sm leading-snug">{ALERT_COPY[lang][info.alert].advice}</p>
              <div className="text-xs text-zinc-500">{t("streetRisk")}</div>
              <SusceptibilityBar pct={info.susceptibility_percentile} label={t(`sus_${info.street_susceptibility}`)} />
              <p className="text-xs text-zinc-500">{t("pctNote", { p: info.susceptibility_percentile })}</p>
            </div>
          )}
          <button onClick={clearPick} className="mt-2 text-xs text-zinc-500 underline">{t("close")}</button>
        </div>
      )}
    </Card>
  );
}

function SusceptibilityBar({ pct, label }: { pct: number; label: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="relative h-2 flex-1 rounded-full bg-gradient-to-r from-emerald-400 via-amber-300 to-red-600">
        <div className="absolute -top-1 h-4 w-1.5 -translate-x-1/2 rounded-sm bg-zinc-900 ring-2 ring-white dark:bg-white dark:ring-zinc-900" style={{ left: `${pct}%` }} />
      </div>
      <span className="w-20 text-right text-xs font-semibold">{label}</span>
    </div>
  );
}

export function StreetsToWatch({ onSelect }: { onSelect: (lat: number, lon: number) => void }) {
  const { bulletin: b, t, lang } = useSentinel();
  if (!b) return null;
  return (
    <Card>
      <h2 className="mb-2 text-sm font-semibold">{t("streetsToWatch")}</h2>
      {b.streets_to_watch.length === 0 ? (
        <p className="text-sm text-zinc-500">{t("noStreets")}</p>
      ) : (
        <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
          {b.streets_to_watch.slice(0, 8).map((s) => (
            <li key={s.road}>
              <button onClick={() => onSelect(s.lat, s.lon)} className="flex w-full items-center justify-between gap-2 py-2 text-left text-sm hover:text-blue-600">
                <span className="truncate">{s.road}</span>
                <AlertPill alert={s.alert} label={ALERT_COPY[lang][s.alert].title} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

const CATS = ["waterlogging", "blocked_drain", "tree_fall", "road_closed", "other"] as const;
const DEPTHS = ["ankle", "knee", "waist", "unknown"] as const;

export function ReportSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t, picked, lang, bumpReports } = useSentinel();
  const [cat, setCat] = useState<(typeof CATS)[number]>("waterlogging");
  const [depth, setDepth] = useState<(typeof DEPTHS)[number]>("unknown");
  const [note, setNote] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "done" | "error">("idle");
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  const submit = async () => {
    if (!picked) return;
    setState("sending");
    try {
      await api.sendReport({ lat: picked.lat, lon: picked.lon, category: cat, depth, note, lang });
      setState("done");
      bumpReports();
      setNote("");
    } catch {
      setState("error");
    }
  };
  const chip = (active: boolean) =>
    `rounded-full border px-3 py-1.5 text-sm transition ${
      active ? "border-blue-600 bg-blue-600 text-white" : "border-zinc-300 hover:border-zinc-400 dark:border-zinc-700"
    }`;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center" onClick={onClose}>
      <div
        role="dialog" aria-modal="true" aria-labelledby="report-title"
        className="w-full max-w-md rounded-t-3xl bg-white p-5 shadow-2xl sm:rounded-3xl dark:bg-zinc-900"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-zinc-300 sm:hidden" />
        <h2 id="report-title" className="text-lg font-bold">{t("reportTitle")}</h2>
        <p className={`mt-1 text-xs ${picked ? "text-zinc-500" : "font-medium text-amber-600"}`}>
          {picked ? `${t("reportWhere")} (${picked.lat.toFixed(4)}, ${picked.lon.toFixed(4)})` : t("reportPick")}
        </p>
        {state === "done" ? (
          <div className="mt-4 rounded-xl bg-emerald-50 p-4 text-sm text-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200">{t("thanks")}</div>
        ) : (
          <>
            <div className="mt-4 flex flex-wrap gap-2">
              {CATS.map((c) => (
                <button key={c} className={chip(cat === c)} onClick={() => setCat(c)} aria-pressed={cat === c}>
                  {t(`cat_${c}`)}
                </button>
              ))}
            </div>
            <div className="mt-4 text-sm font-medium">{t("depth")}</div>
            <div className="mt-2 flex flex-wrap gap-2">
              {DEPTHS.map((d) => (
                <button key={d} className={chip(depth === d)} onClick={() => setDepth(d)} aria-pressed={depth === d}>
                  {t(`depth_${d}`)}
                </button>
              ))}
            </div>
            <label className="mt-4 block text-sm font-medium" htmlFor="note">{t("note")}</label>
            <textarea
              id="note" value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} rows={2}
              className="mt-1 w-full rounded-xl border border-zinc-300 bg-transparent p-2 text-sm outline-none focus:border-blue-600 dark:border-zinc-700"
            />
            {state === "error" && <p className="mt-2 text-sm text-red-600">{t("apiDown")}</p>}
          </>
        )}
        <div className="mt-4 flex gap-2">
          <button onClick={onClose} className="flex-1 rounded-xl border border-zinc-300 px-4 py-2.5 text-sm font-medium dark:border-zinc-700">
            {t("close")}
          </button>
          {state !== "done" && (
            <button
              onClick={submit} disabled={!picked || state === "sending"}
              className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
            >
              {state === "sending" && <Spinner />}
              {state === "sending" ? t("sending") : t("submit")}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function alertLabels(lang: "en" | "mr" | "hi"): Record<Alert, string> {
  return {
    green: ALERT_COPY[lang].green.title,
    yellow: ALERT_COPY[lang].yellow.title,
    orange: ALERT_COPY[lang].orange.title,
    red: ALERT_COPY[lang].red.title,
  };
}
