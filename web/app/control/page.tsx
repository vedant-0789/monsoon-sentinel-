"use client";

import { useEffect, useMemo, useState } from "react";
import RiskMap from "@/components/MapClient";
import { Drivers, alertLabels } from "@/components/panels";
import { ALERT_STYLE, AlertIcon, AlertPill, Card, Gauge, Legend, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { ALERT_COPY } from "@/lib/i18n";
import { useSentinel } from "@/lib/store";
import type { Alert, CitizenReport, Zone } from "@/lib/types";

const ALERTS: Alert[] = ["red", "orange", "yellow", "green"];

export default function ControlRoom() {
  const { bulletin: b, roads, mode, date, t, lang, loading, error, reportsVersion } = useSentinel();
  const [zones, setZones] = useState<Zone[]>([]);
  const [reports, setReports] = useState<CitizenReport[]>([]);
  const [hideGreen, setHideGreen] = useState(true);
  const [fly, setFly] = useState<{ lat: number; lon: number; zoom?: number; key: number } | null>(null);

  useEffect(() => {
    let alive = true;
    api.actions(mode, date, 10).then((z) => alive && setZones(z)).catch(() => alive && setZones([]));
    return () => {
      alive = false;
    };
  }, [mode, date]);

  useEffect(() => {
    const load = () => api.reports(72).then(setReports).catch(() => {});
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, [reportsVersion]);

  const total = useMemo(() => (b ? Object.values(b.road_alert_counts).reduce((s, v) => s + v, 0) : 0), [b]);
  const labels = alertLabels(lang);
  const go = (lat: number, lon: number, zoom = 14.5) => setFly((f) => ({ lat, lon, zoom, key: (f?.key ?? 0) + 1 }));

  return (
    <div className="grid h-full min-h-0 grid-rows-[auto_1fr] gap-3 p-3">
      {/* KPI strip */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
        <div className={`col-span-2 flex items-center gap-3 rounded-2xl px-4 py-3 shadow-sm ${b ? `${ALERT_STYLE[b.headline_alert].bg} ${ALERT_STYLE[b.headline_alert].text}` : "bg-zinc-200"}`}>
          {b ? <AlertIcon alert={b.headline_alert} className="h-9 w-9" /> : <Spinner />}
          <div className="min-w-0">
            <div className="text-lg font-bold leading-tight">{b ? ALERT_COPY[lang][b.headline_alert].title : t("loading")}</div>
            <div className="truncate text-xs opacity-90">
              Pune · {b?.date} · {mode === "live" ? `${t("issued")} ${b?.issued_at ?? ""}` : t("replay")}
            </div>
          </div>
        </div>
        <Card className="flex items-center gap-3 !p-3">
          {b && <Gauge value={b.heavy_rain.probability} alert={b.headline_alert} size={56} />}
          <div className="text-xs leading-snug text-zinc-500">{t("heavyRainChance")}</div>
        </Card>
        {(["red", "orange", "yellow"] as Alert[]).map((a) => (
          <Card key={a} className="!p-3">
            <div className="flex items-center justify-between">
              <AlertPill alert={a} label={labels[a]} />
              <span className="text-[11px] text-zinc-500">{total ? `${Math.round(((b?.road_alert_counts[a] ?? 0) / total) * 100)}%` : ""}</span>
            </div>
            <div className="mt-1 text-2xl font-bold tabular-nums">{(b?.road_alert_counts[a] ?? 0).toLocaleString("en-IN")}</div>
            <div className="text-[11px] text-zinc-500">{t("roadsByAlert")}</div>
          </Card>
        ))}
      </div>

      <div className="grid min-h-0 gap-3 lg:grid-cols-[1fr_380px]">
        {/* Map */}
        <div className="relative min-h-[50vh] overflow-hidden rounded-2xl border border-zinc-200 shadow-sm dark:border-zinc-800">
          <RiskMap roads={roads} hotspots={b?.hotspots} reports={reports} zones={zones} flyTo={fly} hideGreen={hideGreen} />
          <div className="absolute left-3 top-3 space-y-2">
            <Legend title={t("legend")} labels={labels} />
            <div className="flex flex-col gap-1 rounded-xl bg-white/95 px-3 py-2 text-xs shadow-md dark:bg-zinc-900/95">
              <span className="flex items-center gap-2"><span className="h-3 w-3 rounded-full border-2 border-zinc-900" />{t("hotspots")}</span>
              <span className="flex items-center gap-2"><span className="h-3 w-3 rounded-full border-2 border-white bg-blue-600" />{t("reports")}</span>
              <span className="flex items-center gap-2"><span className="flex h-4 w-4 items-center justify-center rounded-full border border-zinc-900 text-[9px] font-bold">1</span>{t("zones")}</span>
              <label className="mt-1 flex cursor-pointer items-center gap-2 border-t border-zinc-200 pt-1 dark:border-zinc-700">
                <input type="checkbox" checked={hideGreen} onChange={(e) => setHideGreen(e.target.checked)} />
                {t("hideGreen")}
              </label>
            </div>
          </div>
          {(loading || error) && (
            <div className="absolute right-3 top-3 rounded-full bg-white/95 px-3 py-1.5 text-xs shadow dark:bg-zinc-900/95">
              {error ? <span className="text-red-600">{t("apiDown")}</span> : <span className="flex items-center gap-2"><Spinner className="h-3.5 w-3.5" />{t("loading")}</span>}
            </div>
          )}
        </div>

        {/* Right rail */}
        <div className="min-h-0 space-y-3 overflow-y-auto pr-1">
          <Card>
            <div className="mb-2 flex items-baseline justify-between">
              <h2 className="text-sm font-semibold">{t("zones")}</h2>
              <span className="text-[11px] text-zinc-500">DBSCAN · 250 m</span>
            </div>
            {zones.length === 0 ? (
              <p className="text-sm text-zinc-500">{t("noStreets")}</p>
            ) : (
              <ol className="space-y-2">
                {zones.map((z) => (
                  <li key={z.zone}>
                    <button onClick={() => go(z.lat, z.lon)} className="flex w-full gap-3 rounded-xl border border-zinc-200 p-2.5 text-left transition hover:border-zinc-400 dark:border-zinc-800">
                      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-zinc-900 text-xs font-bold text-white dark:bg-white dark:text-zinc-900">{z.rank}</span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-semibold">{z.area_label}</span>
                        <span className="block text-xs text-zinc-500">{t(`act_${z.action}`)}</span>
                        <span className="mt-1 flex gap-2 text-[11px]">
                          <span className="font-semibold text-red-700 dark:text-red-400">{t("nRed", { n: z.red_segments })}</span>
                          <span className="text-orange-600">{t("nOrange", { n: z.orange_segments })}</span>
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ol>
            )}
          </Card>

          {b && (
            <Card>
              <h2 className="mb-2 text-sm font-semibold">{t("rainCells")}</h2>
              <CellGrid cells={b.cells} />
              <div className="mt-3"><Drivers /></div>
            </Card>
          )}

          {b && (
            <Card>
              <h2 className="mb-2 text-sm font-semibold">{t("hotspots")}</h2>
              <ul className="max-h-64 divide-y divide-zinc-100 overflow-y-auto dark:divide-zinc-800">
                {[...b.hotspots]
                  .sort((x, y) => ALERTS.indexOf(x.alert) - ALERTS.indexOf(y.alert))
                  .map((h) => (
                    <li key={h.name}>
                      <button onClick={() => go(h.lat, h.lon, 15.5)} className="flex w-full items-center justify-between gap-2 py-1.5 text-left text-sm hover:text-blue-600">
                        <span className="truncate">{h.name}</span>
                        <AlertPill alert={h.alert} label={labels[h.alert]} />
                      </button>
                    </li>
                  ))}
              </ul>
            </Card>
          )}

          <Card>
            <h2 className="mb-2 text-sm font-semibold">{t("reports")}</h2>
            {reports.length === 0 ? (
              <p className="text-sm text-zinc-500">{t("noReports")}</p>
            ) : (
              <ul className="space-y-1.5">
                {reports.slice(0, 12).map((r) => (
                  <li key={r.id}>
                    <button onClick={() => go(r.lat, r.lon, 15.5)} className="w-full rounded-lg px-2 py-1.5 text-left text-sm hover:bg-zinc-100 dark:hover:bg-zinc-800">
                      <span className="font-medium">{t(`cat_${r.category}`)}</span>
                      {r.depth !== "unknown" && <span className="text-zinc-500"> · {t(`depth_${r.depth}`)}</span>}
                      <span className="block text-[11px] text-zinc-500">
                        {new Date(r.created_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}
                        {r.note && ` · “${r.note}”`}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <p className="px-1 text-[11px] text-zinc-500">{t("sources")}</p>
        </div>
      </div>
    </div>
  );
}

function CellGrid({ cells }: { cells: { lat: number; lon: number; probability: number; observed_rain_mm: number | null }[] }) {
  const lats = [...new Set(cells.map((c) => c.lat))].sort((a, b) => b - a);
  const lons = [...new Set(cells.map((c) => c.lon))].sort((a, b) => a - b);
  const get = (la: number, lo: number) => cells.find((c) => c.lat === la && c.lon === lo);
  const shade = (p: number) => `rgba(200,30,30,${0.08 + p * 0.85})`;
  return (
    <div>
      <div className="grid gap-1" style={{ gridTemplateColumns: `repeat(${lons.length}, minmax(0,1fr))` }}>
        {lats.map((la) =>
          lons.map((lo) => {
            const c = get(la, lo);
            const p = c?.probability ?? 0;
            return (
              <div
                key={`${la}-${lo}`}
                className={`rounded-md px-1 py-1.5 text-center ${p > 0.45 ? "text-white" : ""}`}
                style={{ background: shade(p) }}
                title={`${la}°N ${lo}°E${c?.observed_rain_mm != null ? ` · observed ${c.observed_rain_mm} mm` : ""}`}
              >
                <div className="text-sm font-bold tabular-nums">{Math.round(p * 100)}%</div>
                {c?.observed_rain_mm != null && <div className="text-[10px] opacity-80">{c.observed_rain_mm.toFixed(0)} mm</div>}
              </div>
            );
          }),
        )}
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-zinc-500">
        <span>← Western Ghats (Mulshi, Khadakwasla)</span>
        <span>East (Hadapsar) →</span>
      </div>
    </div>
  );
}
