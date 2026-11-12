import type { AlertsSummary, Bulletin, CitizenReport, Classification, HistoryPoint, Mode, Outlook, PointInfo, ReplayDay, Zone } from "./types";

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

async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    let msg = `${r.status}`;
    try {
      const d = (await r.json()).detail;
      msg = typeof d === "string" ? d : JSON.stringify(d);
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
  history: (mode: Mode, date?: string | null) => get<HistoryPoint[]>(`/api/history?${qs(mode, date)}`),
  outlook: (mode: Mode, date?: string | null) => get<Outlook>(`/api/outlook?${qs(mode, date)}`),
  alertsSummary: () => get<AlertsSummary>(`/api/alerts/summary`),
  reportPhotoUrl: (id: number) => `${API_URL}/api/reports/${id}/photo`,
  subscribe: (body: { channel: "telegram" | "sms" | "whatsapp"; phone?: string; lang: string; lat: number; lon: number;
    label: string; min_alert: string; consent: boolean }) =>
    post<{ id: number; status: string; demo_code?: string; telegram_link?: string | null; token?: string }>("/api/subscribe", body),
  subscriptionStatus: (id: number, token: string) =>
    get<{ verified: boolean; active: boolean }>(`/api/subscribe/${id}/status?token=${encodeURIComponent(token)}`),
  verifySubscription: (id: number, code: string) =>
    post<{ status: string; unsubscribe_url?: string }>("/api/subscribe/verify", { id, code }),
  modelCard: () => get<Record<string, unknown>>(`/api/model-card`),
  classify: async (text: string): Promise<Classification> => {
    const r = await fetch(`${API_URL}/api/classify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    return r.ok ? r.json() : {};
  },
  reports: (hours = 72) => get<CitizenReport[]>(`/api/reports?hours=${hours}`),
  sendReport: async (body: Omit<CitizenReport, "id" | "created_at" | "auto_category" | "urgent" | "has_photo" |
    "photo_flood_prob" | "photo_verified"> & { photo?: string | null }) => {
    const r = await fetch(`${API_URL}/api/reports`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`${r.status}`);
    return r.json() as Promise<{ id: number; status: string; urgent?: boolean; photo_verdict?: string | null;
      photo_flood_probability?: number | null }>;
  },
};
