"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import { makeT } from "./i18n";
import type { Bulletin, HistoryPoint, Lang, Mode, PointInfo, ReplayDay } from "./types";

interface Picked {
  lat: number;
  lon: number;
  info?: PointInfo;
  loading?: boolean;
  error?: string;
}

interface Ctx {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: ReturnType<typeof makeT>;
  mode: Mode;
  date: string | null;
  setLive: () => void;
  setReplay: (date: string) => void;
  replayDays: ReplayDay[];
  bulletin: Bulletin | null;
  roads: GeoJSON.FeatureCollection | null;
  loading: boolean;
  slow: boolean;
  error: string | null;
  history: HistoryPoint[];
  picked: Picked | null;
  pick: (lat: number, lon: number) => void;
  clearPick: () => void;
  reportsVersion: number;
  bumpReports: () => void;
}

const SentinelContext = createContext<Ctx | null>(null);

const DEFAULT_REPLAY = "2024-07-25";

export function SentinelProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>("en");
  const [mode, setMode] = useState<Mode>("live");
  const [date, setDate] = useState<string | null>(null);
  const [replayDays, setReplayDays] = useState<ReplayDay[]>([]);
  const [bulletin, setBulletin] = useState<Bulletin | null>(null);
  const [roads, setRoads] = useState<GeoJSON.FeatureCollection | null>(null);
  const [loading, setLoading] = useState(true);
  const [slow, setSlow] = useState(false);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [picked, setPicked] = useState<Picked | null>(null);
  const [reportsVersion, setReportsVersion] = useState(0);

  // Restore per-device preferences after hydration (browser-only state, so it cannot be
  // read during the server render without a hydration mismatch).
  useEffect(() => {
    try {
      const l = localStorage.getItem("ms.lang") as Lang | null;
      const d = new URL(window.location.href).searchParams.get("date");
      // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time hydration of browser-only prefs
      if (l === "en" || l === "mr" || l === "hi") setLangState(l);
      if (d) {
        setMode("replay");
        setDate(d);
      }
    } catch {}
    api.replayDays().then(setReplayDays).catch(() => {});
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang === "en" ? "en" : lang === "mr" ? "mr" : "hi";
  }, [lang]);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem("ms.lang", l);
    } catch {}
  }, []);

  const syncUrl = (d: string | null) => {
    try {
      const url = new URL(window.location.href);
      if (d) url.searchParams.set("date", d);
      else url.searchParams.delete("date");
      window.history.replaceState(null, "", url.toString());
    } catch {}
  };

  const loadPoint = useCallback((lat: number, lon: number, m: Mode, d: string | null) => {
    setPicked({ lat, lon, loading: true });
    api
      .point(lat, lon, m, d)
      .then((info) => setPicked({ lat, lon, info }))
      .catch((e: Error) => setPicked({ lat, lon, error: e.message }));
  }, []);

  const switchTo = useCallback(
    (m: Mode, d: string | null) => {
      setMode(m);
      setDate(d);
      setLoading(true);
      setError(null);
      syncUrl(d);
      if (picked) loadPoint(picked.lat, picked.lon, m, d); // re-evaluate the selected street
    },
    [picked, loadPoint],
  );
  const setLive = useCallback(() => switchTo("live", null), [switchTo]);
  const setReplay = useCallback((d: string) => switchTo("replay", d || DEFAULT_REPLAY), [switchTo]);

  useEffect(() => {
    let alive = true;
    // free hosting sleeps when idle: tell people the first load may take a while
    const slowTimer = setTimeout(() => alive && setSlow(true), 4000);
    api.history(mode, date).then((h) => alive && setHistory(h)).catch(() => alive && setHistory([]));
    Promise.all([api.bulletin(mode, date), api.roads(mode, date)])
      .then(([b, r]) => {
        if (!alive) return;
        setBulletin(b);
        setRoads(r);
      })
      .catch((e: Error) => alive && setError(e.message))
      .finally(() => {
        clearTimeout(slowTimer);
        if (alive) {
          setLoading(false);
          setSlow(false);
        }
      });
    return () => {
      alive = false;
      clearTimeout(slowTimer);
    };
  }, [mode, date]);

  const pick = useCallback((lat: number, lon: number) => loadPoint(lat, lon, mode, date), [loadPoint, mode, date]);

  const value = useMemo<Ctx>(
    () => ({
      lang, setLang, t: makeT(lang), mode, date, setLive, setReplay, replayDays, bulletin, roads, loading, slow, error, history,
      picked, pick, clearPick: () => setPicked(null), reportsVersion, bumpReports: () => setReportsVersion((v) => v + 1),
    }),
    [lang, setLang, mode, date, setLive, setReplay, replayDays, bulletin, roads, loading, slow, error, history, picked, pick, reportsVersion],
  );
  return <SentinelContext.Provider value={value}>{children}</SentinelContext.Provider>;
}

export function useSentinel() {
  const c = useContext(SentinelContext);
  if (!c) throw new Error("useSentinel must be used inside SentinelProvider");
  return c;
}
