"use client";

import { useState } from "react";
import RiskMap from "@/components/MapClient";
import { AlertHero, ReportSheet, StreetCheck, StreetsToWatch, alertLabels } from "@/components/panels";
import { Legend, Spinner } from "@/components/ui";
import { useSentinel } from "@/lib/store";

export default function CitizenPage() {
  const { roads, bulletin, picked, pick, t, lang, loading } = useSentinel();
  const [fly, setFly] = useState<{ lat: number; lon: number; key: number } | null>(null);
  const [reportOpen, setReportOpen] = useState(false);

  const goTo = (lat: number, lon: number) => {
    setFly((f) => ({ lat, lon, key: (f?.key ?? 0) + 1 }));
    pick(lat, lon);
  };

  return (
    <div className="flex h-full flex-col-reverse lg:grid lg:grid-cols-[420px_1fr]">
      <aside className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3 pb-24 lg:pb-3">
        <AlertHero />
        <StreetCheck onLocate={goTo} />
        <StreetsToWatch onSelect={goTo} />
        <p className="px-1 text-[11px] leading-snug text-zinc-500">{t("sources")}</p>
      </aside>

      <div className="relative h-[46vh] shrink-0 lg:h-full">
        <RiskMap
          roads={roads}
          hotspots={bulletin?.hotspots}
          picked={picked}
          flyTo={fly}
          onPick={(lat, lon) => pick(lat, lon)}
        />
        <div className="pointer-events-none absolute left-3 top-3 flex flex-col gap-2">
          <div className="pointer-events-auto">
            <Legend title={t("legend")} labels={alertLabels(lang)} />
          </div>
          {loading && (
            <div className="pointer-events-auto flex w-fit items-center gap-2 rounded-full bg-white/95 px-3 py-1.5 text-xs shadow dark:bg-zinc-900/95">
              <Spinner className="h-3.5 w-3.5" /> {t("loading")}
            </div>
          )}
        </div>
        <button
          onClick={() => setReportOpen(true)}
          className="fixed bottom-5 right-5 z-30 flex items-center gap-2 rounded-full bg-zinc-900 px-5 py-3 text-sm font-semibold text-white shadow-xl transition hover:bg-zinc-800 active:scale-95 lg:absolute dark:bg-white dark:text-zinc-900"
        >
          <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden>
            <path d="M12 3c3.5 4.6 6.5 8.2 6.5 11.7a6.5 6.5 0 0 1-13 0C5.5 11.2 8.5 7.6 12 3z" fill="currentColor" />
          </svg>
          {t("report")}
        </button>
      </div>
      <ReportSheet open={reportOpen} onClose={() => setReportOpen(false)} />
    </div>
  );
}
