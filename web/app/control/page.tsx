"use client";

import { useEffect, useMemo, useState } from "react";
import { Timeline } from "@/components/charts";
import { OutlookCard } from "@/components/features";
import RiskMap from "@/components/MapClient";
import { Drivers, alertLabels } from "@/components/panels";
import { ALERT_STYLE, AlertIcon, AlertPill, Card, Gauge, Legend, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { ALERT_COPY } from "@/lib/i18n";
import { useSentinel } from "@/lib/store";
import type { Alert, AlertsSummary, CitizenReport, FacilityKind, Zone } from "@/lib/types";

const ALERTS: Alert[] = ["red", "orange", "yellow", "green"];
const FAC_ORDER: FacilityKind[] = ["hospital", "fire_station", "clinic", "police", "school", "college"];
const FAC_ICON: Record<FacilityKind, string> = {
  hospital: "🏥", clinic: "⚕️", school: "🏫", college: "🎓", police: "🚓", fire_station: "🚒",
};

export default function ControlRoom() {
  const { bulletin: b, roads, mode, date, t, lang, loading, slow, error, reportsVersion, history } = useSentinel();
  const [zones, setZones] = useState<Zone[]>([]);
  const [reports, setReports] = useState<CitizenReport[]>([]);
  const [hideGreen, setHideGreen] = useState(true);
  const [showFac, setShowFac] = useState(true);
  const [fly, setFly] = useState<{ lat: number; lon: number; zoom?: number; key: number } | null>(null);
  const [subs, setSubs] = useState<AlertsSummary | null>(null);

  useEffect(() => {
    api.alertsSummary().then(setSubs).catch(() => setSubs(null));
  }, [reportsVersion]);

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
  const impact = b?.impact;
  const pumpsUsed = zones.filter((z) => z.rl_deploy_pump).length;

  return (
    <div className="grid h-full min-h-0 grid-rows-[auto_1fr] gap-3 p-3">
      {/* KPI strip */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
        <div className={`col-span-2 flex items-center gap-3 rounded-2xl px-4 py-3 shadow-sm ${b ? `${ALERT_STYLE[b.headline_alert].bg} ${ALERT_STYLE[b.headline_alert].text}` : "bg-zinc-200 dark:bg-zinc-800"}`}>
          {b ? <AlertIcon alert={b.headline_alert} className="h-9 w-9" /> : <Spinner />}
          <div className="min-w-0">
            <div className="text-lg font-bold leading-tight">{b ? ALERT_COPY[lang][b.headline_alert].title : slow ? t("waking") : t("loading")}</div>
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

      <div className="grid min-h-0 gap-3 lg:grid-cols-[1fr_400px]">
        {/* Map */}
        <div className="relative min-h-[55vh] overflow-hidden rounded-2xl border border-zinc-200 shadow-sm dark:border-zinc-800">
          <RiskMap roads={roads} hotspots={b?.hotspots} reports={reports} zones={zones}
            facilities={showFac ? impact?.facilities : []} flyTo={fly} hideGreen={hideGreen} />
          <div className="absolute left-3 top-3 space-y-2">
            <Legend title={t("legend")} labels={labels} />
            <div className="flex flex-col gap-1 rounded-xl bg-white/95 px-3 py-2 text-xs shadow-md dark:bg-zinc-900/95">
              <span className="flex items-center gap-2"><span className="h-3 w-3 rounded-full border-2 border-zinc-900 dark:border-white" />{t("hotspots")}</span>
              <span className="flex items-center gap-2"><span className="h-3 w-3 rounded-full border-2 border-white bg-blue-600" />{t("reports")}</span>
              <span className="flex items-center gap-2"><span className="h-3 w-3 rounded-full border-2 border-red-600 bg-violet-600" />{t("showFacilities")}</span>
              <span className="flex items-center gap-2"><span className="flex h-4 w-4 items-center justify-center rounded-full bg-red-600 text-[8px] font-bold text-white">1</span>{t("deployPump")}</span>
              <div className="mt-1 space-y-1 border-t border-zinc-200 pt-1 dark:border-zinc-700">
                <label className="flex cursor-pointer items-center gap-2">
                  <input type="checkbox" checked={hideGreen} onChange={(e) => setHideGreen(e.target.checked)} />
                  {t("hideGreen")}
                </label>
                <label className="flex cursor-pointer items-center gap-2">
                  <input type="checkbox" checked={showFac} onChange={(e) => setShowFac(e.target.checked)} />
                  {t("showFacilities")}
                </label>
              </div>
            </div>
          </div>
          {(loading || error) && (
            <div className="absolute right-3 top-3 max-w-xs rounded-2xl bg-white/95 px-3 py-1.5 text-xs shadow dark:bg-zinc-900/95">
              {error ? <span className="text-red-600">{t("apiDown")}</span> : (
                <span className="flex items-center gap-2"><Spinner className="h-3.5 w-3.5" />{slow ? t("waking") : t("loading")}</span>
              )}
            </div>
          )}
        </div>

        {/* Right rail */}
        <div className="min-h-0 space-y-3 overflow-y-auto pr-1">
          {/* Response zones + RL pump plan */}
          <Card>
            <div className="mb-2 flex items-baseline justify-between gap-2">
              <h2 className="text-sm font-semibold">{t("zones")}</h2>
              <span className="text-[11px] text-zinc-500">{t("pumpPlan")}</span>
            </div>
            {zones.length > 0 && (
              <div className="mb-3 flex items-center gap-2 rounded-xl bg-red-50 px-3 py-2 text-xs text-red-900 dark:bg-red-950/40 dark:text-red-200">
                <span className="text-base" aria-hidden>🚰</span>
                <span className="font-semibold">{t("pumpsDeployed", { n: pumpsUsed, k: 5 })}</span>
              </div>
            )}
            {zones.length === 0 ? (
              <p className="text-sm text-zinc-500">{t("noStreets")}</p>
            ) : (
              <ol className="space-y-2">
                {zones.map((z) => (
                  <li key={z.zone}>
                    <button onClick={() => go(z.lat, z.lon)}
                      className={`flex w-full gap-3 rounded-xl border p-2.5 text-left transition hover:border-zinc-400 ${z.rl_deploy_pump ? "border-red-300 dark:border-red-900" : "border-zinc-200 dark:border-zinc-800"}`}>
                      <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white ${z.rl_deploy_pump ? "bg-red-600" : "bg-zinc-900 dark:bg-zinc-600"}`}>{z.rank}</span>
                      <span className="min-w-0 flex-1">
                        <span className="flex items-center justify-between gap-2">
                          <span className="truncate text-sm font-semibold">{z.area_label}</span>
                          <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ${z.rl_deploy_pump ? "bg-red-600 text-white" : "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"}`}>
                            {z.rl_deploy_pump ? t("deployPump") : t("holdReserve")}
                          </span>
                        </span>
                        <span className="block text-xs text-zinc-500">{t(`act_${z.action}`)}</span>
                        <span className="mt-1 flex flex-wrap gap-x-2 text-[11px]">
                          <span className="font-semibold text-red-700 dark:text-red-400">{t("nRed", { n: z.red_segments })}</span>
                          <span className="text-orange-600">{t("nOrange", { n: z.orange_segments })}</span>
                          {z.depot && <span className="text-zinc-500">🚒 {t("fromDepot", { d: z.depot, km: z.depot_km ?? "" })}</span>}
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ol>
            )}
          </Card>

          <OutlookCard compact />

          {subs && (
            <Card className="!p-3">
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="rounded-lg bg-emerald-50 px-2 py-1.5 dark:bg-emerald-950/40">
                  <div className="text-emerald-900/70 dark:text-emerald-200/70">{t("subscribers")}</div>
                  <div className="text-lg font-bold tabular-nums text-emerald-800 dark:text-emerald-200">
                    {Object.values(subs.active_subscribers).reduce((a, b) => a + b, 0)}
                  </div>
                  <div className="text-[10px] text-zinc-500">
                    WhatsApp {subs.active_subscribers.whatsapp ?? 0} · SMS {subs.active_subscribers.sms ?? 0}
                  </div>
                </div>
                <div className="rounded-lg bg-zinc-100 px-2 py-1.5 dark:bg-zinc-800">
                  <div className="text-zinc-500">{t("sentToday")}</div>
                  <div className="text-lg font-bold tabular-nums">
                    {(subs.sent_today.sent ?? 0) + (subs.sent_today.dry_run ?? 0)}
                  </div>
                  {(subs.dry_run || !Object.values(subs.providers).some(Boolean)) && (
                    <div className="text-[10px] text-zinc-500">{t("dryRunNote")}</div>
                  )}
                </div>
              </div>
            </Card>
          )}

          {/* Impact */}
          {impact && (
            <Card>
              <h2 className="mb-2 text-sm font-semibold">{t("impact")}</h2>
              <div className="mb-3 grid grid-cols-2 gap-2">
                <div className="rounded-xl bg-red-50 px-3 py-2 dark:bg-red-950/40">
                  <div className="text-xl font-bold tabular-nums text-red-700 dark:text-red-300">{impact.red_road_km}</div>
                  <div className="text-[11px] text-red-900/70 dark:text-red-200/70">{t("roadKmRed")}</div>
                </div>
                <div className="rounded-xl bg-orange-50 px-3 py-2 dark:bg-orange-950/40">
                  <div className="text-xl font-bold tabular-nums text-orange-700 dark:text-orange-300">{impact.orange_road_km}</div>
                  <div className="text-[11px] text-orange-900/70 dark:text-orange-200/70">{t("roadKmOrange")}</div>
                </div>
              </div>
              <div className="text-xs text-zinc-500">{t("facilitiesAtRisk")}</div>
              {Object.keys(impact.facilities_at_risk).length === 0 ? (
                <p className="mt-1 text-sm text-zinc-500">{t("noFacilities")}</p>
              ) : (
                <>
                  <div className="mt-2 grid grid-cols-3 gap-1.5">
                    {FAC_ORDER.filter((k) => impact.facilities_at_risk[k]).map((k) => (
                      <div key={k} className="rounded-lg bg-zinc-100 px-2 py-1.5 text-center dark:bg-zinc-800">
                        <div className="text-sm" aria-hidden>{FAC_ICON[k]}</div>
                        <div className="text-sm font-bold tabular-nums">{impact.facilities_at_risk[k]}</div>
                        <div className="text-[10px] text-zinc-500">{t(`fac_${k}`)}</div>
                      </div>
                    ))}
                  </div>
                  <ul className="mt-2 max-h-48 divide-y divide-zinc-100 overflow-y-auto dark:divide-zinc-800">
                    {impact.facilities.slice(0, 20).map((f, i) => (
                      <li key={`${f.name}-${i}`}>
                        <button onClick={() => go(f.lat, f.lon, 16)} className="flex w-full items-center justify-between gap-2 py-1.5 text-left text-sm hover:text-blue-600">
                          <span className="truncate"><span aria-hidden>{FAC_ICON[f.kind]} </span>{f.name}</span>
                          <AlertPill alert={f.alert} label={labels[f.alert]} />
                        </button>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </Card>
          )}

          {b && (
            <Card>
              <h2 className="mb-2 text-sm font-semibold">{t("rainCells")}</h2>
              <CellGrid cells={b.cells} />
              {history.length > 0 && (
                <div className="mt-3">
                  <div className="mb-1 text-xs font-semibold">{t("last14")}</div>
                  <Timeline data={history} labels={{ rain: t("rainBars"), chance: t("chanceLine") }} />
                </div>
              )}
              <div className="mt-3"><Drivers /></div>
            </Card>
          )}

          <Card>
            <h2 className="mb-2 text-sm font-semibold">{t("reports")}</h2>
            {reports.length === 0 ? (
              <p className="text-sm text-zinc-500">{t("noReports")}</p>
            ) : (
              <ul className="space-y-1.5">
                {reports.slice(0, 15).map((r) => (
                  <li key={r.id}>
                    <button onClick={() => go(r.lat, r.lon, 15.5)} className="flex w-full gap-2 rounded-lg px-2 py-1.5 text-left text-sm hover:bg-zinc-100 dark:hover:bg-zinc-800">
                      {r.has_photo ? (
                        // eslint-disable-next-line @next/next/no-img-element -- photo served by the API
                        <img src={api.reportPhotoUrl(r.id)} alt="" loading="lazy" className="h-12 w-12 shrink-0 rounded-md object-cover" />
                      ) : null}
                      <span className="min-w-0 flex-1">
                      <span className="flex flex-wrap items-center gap-2">
                        {r.urgent ? <span className="rounded-full bg-red-600 px-1.5 py-0.5 text-[10px] font-semibold text-white">{t("urgent")}</span> : null}
                        <span className="font-medium">{t(`cat_${r.category}`)}</span>
                        {r.depth !== "unknown" && <span className="text-zinc-500">· {t(`depth_${r.depth}`)}</span>}
                        {r.photo_verified === 1 && (
                          <span className="rounded-full bg-emerald-600 px-1.5 py-0.5 text-[10px] font-semibold text-white">✓ {t("verifiedPhoto")}</span>
                        )}
                      </span>
                      <span className="block text-[11px] text-zinc-500">
                        {new Date(r.created_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}
                        {r.note && ` · “${r.note}”`}
                      </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>

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
              <div key={`${la}-${lo}`} className={`rounded-md px-1 py-1.5 text-center ${p > 0.45 ? "text-white" : ""}`}
                style={{ background: shade(p) }}
                title={`${la}°N ${lo}°E${c?.observed_rain_mm != null ? ` · observed ${c.observed_rain_mm} mm` : ""}`}>
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
