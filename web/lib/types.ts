export type Alert = "green" | "yellow" | "orange" | "red";
export type Mode = "live" | "replay";
export type Lang = "en" | "mr" | "hi";

export interface Driver {
  factor: string;
  effect: "raises" | "lowers";
  strength: number;
}

export interface Bulletin {
  mode: Mode;
  date: string;
  issued_at: string;
  in_season: boolean;
  headline_alert: Alert;
  headline_text: string;
  heavy_rain: {
    probability: number;
    model_probability: number;
    likelihood: string;
    nwp_rain_24h_mm: number | null;
    observed_rain_mm: number | null;
    rain_last_3_days_mm: number | null;
    drivers: Driver[];
  };
  cells: { lat: number; lon: number; probability: number; observed_rain_mm: number | null; nwp_rain_24h_mm: number | null }[];
  road_alert_counts: Record<Alert, number>;
  streets_to_watch: { road: string; alert: Alert; lat: number; lon: number }[];
  hotspots: { name: string; type: string; alert: Alert; lat: number; lon: number; source: string }[];
}

export interface PointInfo {
  nearest_road: string;
  distance_m: number;
  alert: Alert;
  advice: string;
  street_susceptibility: "low" | "moderate" | "high" | "very high";
  susceptibility_percentile: number;
  uncertainty_band: [number, number];
  heavy_rain_probability: number | null;
  covered: boolean;
}

export interface Zone {
  rank: number;
  zone: number;
  lat: number;
  lon: number;
  area_label: string;
  red_segments: number;
  orange_segments: number;
  priority_score: number;
  action: "pump" | "crew" | "inspect";
  recommended: string;
}

export interface CitizenReport {
  id: number;
  created_at: string;
  lat: number;
  lon: number;
  category: string;
  depth: string;
  note: string;
  lang: Lang;
}

export interface ReplayDay {
  date: string;
  label: string;
}
