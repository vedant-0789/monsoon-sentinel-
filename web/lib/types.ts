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
  impact?: Impact;
}

export type FacilityKind = "hospital" | "clinic" | "school" | "college" | "police" | "fire_station";

export interface Impact {
  red_road_km: number;
  orange_road_km: number;
  facilities_total: number;
  facilities_at_risk: Partial<Record<FacilityKind, number>>;
  facilities: { name: string; kind: FacilityKind; alert: Alert; lat: number; lon: number }[];
}

export interface HistoryPoint {
  date: string;
  probability: number | null;
  rain_mm: number;
}

export interface Classification {
  category?: string;
  confidence?: number;
  urgent?: boolean;
  urgent_probability?: number;
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
  p_flood?: number;
  depot?: string;
  depot_km?: number;
  rl_deploy_pump?: boolean;
  pumps_left_after?: number;
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
  auto_category?: string | null;
  urgent?: number | boolean;
  has_photo?: number;
  photo_flood_prob?: number | null;
  photo_verified?: number | null;
}

export interface OutlookHour {
  time: string;
  mean: number;
  min: number;
  max: number;
  by_model: Record<string, number | null>;
}

export interface Outlook {
  available: boolean;
  reason?: string;
  source?: string;
  models?: string[];
  window_start_ist?: string;
  total_24h_mm?: { mean: number; min: number; max: number };
  max_3h_mm?: number;
  models_intense?: number;
  intense_watch?: boolean;
  peak_hour_ist?: string | null;
  hours?: OutlookHour[];
}

export interface AlertsSummary {
  active_subscribers: Record<string, number>;
  sent_today: Record<string, number>;
  providers: Record<string, boolean>;
  dry_run: boolean;
}

export interface ReplayDay {
  date: string;
  label: string;
}
