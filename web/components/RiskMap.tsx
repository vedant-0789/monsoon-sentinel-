"use client";

import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource, Map as MLMap, MapLayerMouseEvent, MapMouseEvent } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import { ALERT_HEX } from "@/lib/colors";
import type { Alert, CitizenReport, Zone } from "@/lib/types";

// Turbopack cannot bundle MapLibre 6's module worker; serve it as a static file (see package.json).
maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs");

const STYLES = {
  light: "https://tiles.openfreemap.org/styles/positron",
  dark: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
};
const PUNE: [number, number] = [73.855, 18.515];
const EMPTY: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

export interface MapFacility {
  name: string;
  kind: string;
  alert: Alert;
  lat: number;
  lon: number;
}

interface Props {
  roads: GeoJSON.FeatureCollection | null;
  hotspots?: { name: string; alert: Alert; lat: number; lon: number }[];
  reports?: CitizenReport[];
  zones?: Zone[];
  facilities?: MapFacility[];
  picked?: { lat: number; lon: number } | null;
  flyTo?: { lat: number; lon: number; zoom?: number; key: number } | null;
  onPick?: (lat: number, lon: number) => void;
  hideGreen?: boolean;
  className?: string;
}

const fc = (features: GeoJSON.Feature[]): GeoJSON.FeatureCollection => ({ type: "FeatureCollection", features });
const pt = (lon: number, lat: number, properties: Record<string, unknown>): GeoJSON.Feature => ({
  type: "Feature",
  geometry: { type: "Point", coordinates: [lon, lat] },
  properties,
});

function prefersDark() {
  return typeof window !== "undefined" && !!window.matchMedia?.("(prefers-color-scheme: dark)").matches;
}

function addLayers(m: MLMap, dark: boolean) {
  for (const id of ["roads", "facilities", "hotspots", "reports", "picked"]) {
    if (!m.getSource(id)) m.addSource(id, { type: "geojson", data: EMPTY });
  }
  const colour: maplibregl.ExpressionSpecification = [
    "match", ["get", "a"],
    "red", ALERT_HEX.red, "orange", ALERT_HEX.orange, "yellow", ALERT_HEX.yellow, ALERT_HEX.green,
  ];
  const ring = dark ? "#f4f4f5" : "#111827";
  m.addLayer({
    id: "roads", type: "circle", source: "roads",
    paint: {
      "circle-color": colour,
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 1.4, 13, 3, 16, 7],
      "circle-opacity": ["match", ["get", "a"], "green", dark ? 0.25 : 0.35, "yellow", 0.75, 0.92],
    },
  });
  m.addLayer({
    id: "facilities", type: "circle", source: "facilities", minzoom: 11,
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 11, 3.5, 15, 7],
      "circle-color": "#7c3aed",
      "circle-stroke-color": colour,
      "circle-stroke-width": 2,
    },
  });
  m.addLayer({
    id: "hotspots", type: "circle", source: "hotspots",
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 4, 15, 9],
      "circle-color": "rgba(0,0,0,0)",
      "circle-stroke-color": ring,
      "circle-stroke-width": 2,
    },
  });
  m.addLayer({
    id: "reports", type: "circle", source: "reports",
    paint: {
      "circle-radius": ["case", ["==", ["get", "u"], 1], 8, 6],
      "circle-color": ["case", ["==", ["get", "u"], 1], "#dc2626", "#2563eb"],
      "circle-stroke-color": "#fff",
      "circle-stroke-width": 2,
    },
  });
  m.addLayer({ id: "picked-halo", type: "circle", source: "picked", paint: { "circle-radius": 18, "circle-color": "#2563eb", "circle-opacity": 0.2 } });
  m.addLayer({
    id: "picked", type: "circle", source: "picked",
    paint: { "circle-radius": 7, "circle-color": "#2563eb", "circle-stroke-color": "#fff", "circle-stroke-width": 3 },
  });
}

export default function RiskMap({ roads, hotspots, reports, zones, facilities, picked, flyTo, onPick, hideGreen, className }: Props) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<MLMap | null>(null);
  const ready = useRef(false);
  const markers = useRef<maplibregl.Marker[]>([]);
  const latest = useRef<() => void>(() => {});
  const pickRef = useRef(onPick);
  useEffect(() => {
    pickRef.current = onPick;
  }, [onPick]);

  useEffect(() => {
    if (!el.current) return;
    let dark = prefersDark();
    const m = new maplibregl.Map({
      container: el.current,
      style: dark ? STYLES.dark : STYLES.light,
      center: PUNE,
      zoom: 11.2,
      minZoom: 9,
      maxZoom: 17,
      attributionControl: { compact: true },
    });
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    m.on("style.load", () => {
      addLayers(m, dark);
      ready.current = true;
      latest.current(); // (re)apply the newest data after every style load
    });
    // follow the OS light/dark theme live
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    const onTheme = (e: MediaQueryListEvent) => {
      dark = e.matches;
      ready.current = false;
      m.setStyle(dark ? STYLES.dark : STYLES.light);
    };
    mq?.addEventListener("change", onTheme);

    m.on("click", (e: MapMouseEvent) => pickRef.current?.(e.lngLat.lat, e.lngLat.lng));
    const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10 });
    const esc = (v: unknown) => String(v ?? "").replace(/[&<>"]/g, (c) => `&#${c.charCodeAt(0)};`);
    const hover = (layer: string, html: (p: Record<string, unknown>) => string) => {
      m.on("mouseenter", layer, (e: MapLayerMouseEvent) => {
        m.getCanvas().style.cursor = "pointer";
        const f = e.features?.[0];
        if (f) popup.setLngLat(e.lngLat).setHTML(html(f.properties ?? {})).addTo(m);
      });
      m.on("mouseleave", layer, () => {
        m.getCanvas().style.cursor = "";
        popup.remove();
      });
    };
    hover("hotspots", (p) => `<strong>${esc(p.name)}</strong>`);
    hover("facilities", (p) => `<strong>${esc(p.name)}</strong><br/><span style="opacity:.7">${esc(p.kind).replace("_", " ")}</span>`);
    map.current = m;
    const mk = markers;
    return () => {
      mq?.removeEventListener("change", onTheme);
      mk.current.forEach((x) => x.remove());
      ready.current = false;
      m.remove();
      map.current = null;
    };
  }, []);

  // push data into sources whenever props change
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const apply = () => {
      const roadData = roads && hideGreen ? fc(roads.features.filter((f) => f.properties?.a !== "green")) : roads;
      (m.getSource("roads") as GeoJSONSource | undefined)?.setData(roadData ?? EMPTY);
      (m.getSource("hotspots") as GeoJSONSource | undefined)?.setData(
        fc((hotspots ?? []).map((h) => pt(h.lon, h.lat, { name: h.name, a: h.alert }))),
      );
      (m.getSource("facilities") as GeoJSONSource | undefined)?.setData(
        fc((facilities ?? []).map((f) => pt(f.lon, f.lat, { name: f.name, kind: f.kind, a: f.alert }))),
      );
      (m.getSource("reports") as GeoJSONSource | undefined)?.setData(
        fc((reports ?? []).map((r) => pt(r.lon, r.lat, { c: r.category, u: r.urgent ? 1 : 0 }))),
      );
      (m.getSource("picked") as GeoJSONSource | undefined)?.setData(picked ? fc([pt(picked.lon, picked.lat, {})]) : EMPTY);
      markers.current.forEach((x) => x.remove());
      markers.current = (zones ?? []).map((z) => {
        const d = document.createElement("div");
        d.className = `ms-zone ${z.rl_deploy_pump ? "ms-zone-pump" : ""}`;
        d.textContent = String(z.rank);
        d.title = z.area_label;
        return new maplibregl.Marker({ element: d }).setLngLat([z.lon, z.lat]).addTo(m);
      });
    };
    latest.current = apply;
    if (ready.current) apply();
  }, [roads, hotspots, reports, zones, facilities, picked, hideGreen]);

  useEffect(() => {
    if (flyTo && map.current) map.current.flyTo({ center: [flyTo.lon, flyTo.lat], zoom: flyTo.zoom ?? 15, speed: 1.4 });
  }, [flyTo]);

  return <div ref={el} className={className ?? "h-full w-full"} role="application" aria-label="Map of street alerts" />;
}
