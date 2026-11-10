import type { Bulletin, CitizenReport, Mode, PointInfo, ReplayDay, Zone } from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8077").replace(/\/$/, "");

function qs(mode: Mode, date?: string | null, extra: Record<string, string | number> = {}) {
  const p = new URLSearchParams({ mode, ...Object.fromEntries(Object.entries(extra).map(([k, v]) => [k, String(v)])) });
  if (mode === "replay" && date) p.set("date", date);
  return p.toString();
}

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!r.ok) {
    let msg = `${r.status}`;
    try {
      msg = (await r.json()).detail ?? msg;
    } catch {}
    throw new Error(msg);
  }
  return r.json() as Promise<T>;
}

export const api = {
  bulletin: (mode: Mode, date?: string | null) => get<Bulletin>(`/api/bulletin?${qs(mode, date)}`),
  roads: (mode: Mode, date?: string | null, minAlert = "green") =>
    get<GeoJSON.FeatureCollection>(`/api/roads?${qs(mode, date, { min_alert: minAlert })}`),
  point: (lat: number, lon: number, mode: Mode, date?: string | null) =>
    get<PointInfo>(`/api/point?${qs(mode, date, { lat, lon })}`),
  actions: (mode: Mode, date?: string | null, limit = 10) => get<Zone[]>(`/api/actions?${qs(mode, date, { limit })}`),
  replayDays: () => get<ReplayDay[]>(`/api/replay-days`),
  reports: (hours = 72) => get<CitizenReport[]>(`/api/reports?hours=${hours}`),
  sendReport: async (body: Omit<CitizenReport, "id" | "created_at">) => {
    const r = await fetch(`${API_URL}/api/reports`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`${r.status}`);
    return r.json() as Promise<{ id: number; status: string }>;
  },
};
