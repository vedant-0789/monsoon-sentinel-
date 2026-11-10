"use client";

import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource, Map as MLMap, MapLayerMouseEvent, MapMouseEvent } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import { ALERT_HEX } from "@/lib/colors";
import type { Alert, CitizenReport, Zone } from "@/lib/types";

// Turbopack cannot bundle MapLibre 6's module worker; serve it as a static file (see package.json).
maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs");

const STYLE = "https://tiles.openfreemap.org/styles/positron";
const PUNE: [number, number] = [73.855, 18.515];
const EMPTY: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

interface Props {
  roads: GeoJSON.FeatureCollection | null;
  hotspots?: { name: string; alert: Alert; lat: number; lon: number }[];
  reports?: CitizenReport[];
  zones?: Zone[];
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

export default function RiskMap({ roads, hotspots, reports, zones, picked, flyTo, onPick, hideGreen, className }: Props) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<MLMap | null>(null);
  const ready = useRef(false);
  const pending = useRef<(() => void) | null>(null);
  const pickRef = useRef(onPick);
  useEffect(() => {
    pickRef.current = onPick;
  }, [onPick]);

  useEffect(() => {
    if (!el.current) return;
    const m = new maplibregl.Map({
      container: el.current,
      style: STYLE,
      center: PUNE,
      zoom: 11.2,
      minZoom: 9,
      maxZoom: 17,
      attributionControl: { compact: true },
    });
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    m.on("load", () => {
      m.addSource("roads", { type: "geojson", data: EMPTY });
      m.addSource("hotspots", { type: "geojson", data: EMPTY });
      m.addSource("reports", { type: "geojson", data: EMPTY });
      m.addSource("zones", { type: "geojson", data: EMPTY });
      m.addSource("picked", { type: "geojson", data: EMPTY });
      const colour: maplibregl.ExpressionSpecification = [
        "match", ["get", "a"],
        "red", ALERT_HEX.red, "orange", ALERT_HEX.orange, "yellow", ALERT_HEX.yellow, ALERT_HEX.green,
      ];
      m.addLayer({
        id: "roads",
        type: "circle",
        source: "roads",
        paint: {
          "circle-color": colour,
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 1.4, 13, 3, 16, 7],
          "circle-opacity": ["match", ["get", "a"], "green", 0.35, "yellow", 0.7, 0.9],
        },
      });
      m.addLayer({
        id: "zones",
        type: "circle",
        source: "zones",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 12, 14, 34],
          "circle-color": "#111827",
          "circle-opacity": 0.08,
          "circle-stroke-color": "#111827",
          "circle-stroke-width": 1.5,
        },
      });
      m.addLayer({
        id: "zones-label",
        type: "symbol",
        source: "zones",
        layout: { "text-field": ["get", "rank"], "text-size": 13, "text-font": ["Noto Sans Bold"] },
        paint: { "text-color": "#111827", "text-halo-color": "#fff", "text-halo-width": 1.5 },
      });
      m.addLayer({
        id: "hotspots",
        type: "circle",
        source: "hotspots",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 4, 15, 9],
          "circle-color": "rgba(0,0,0,0)",
          "circle-stroke-color": "#111827",
          "circle-stroke-width": 2,
        },
      });
      m.addLayer({
        id: "reports",
        type: "circle",
        source: "reports",
        paint: {
          "circle-radius": 6,
          "circle-color": "#2563eb",
          "circle-stroke-color": "#fff",
          "circle-stroke-width": 2,
        },
      });
      m.addLayer({
        id: "picked-halo",
        type: "circle",
        source: "picked",
        paint: { "circle-radius": 18, "circle-color": "#2563eb", "circle-opacity": 0.18 },
      });
      m.addLayer({
        id: "picked",
        type: "circle",
        source: "picked",
        paint: { "circle-radius": 7, "circle-color": "#2563eb", "circle-stroke-color": "#fff", "circle-stroke-width": 3 },
      });
      ready.current = true;
      pending.current?.();
      pending.current = null;
    });
    m.on("click", (e: MapMouseEvent) => pickRef.current?.(e.lngLat.lat, e.lngLat.lng));

    const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10 });
    m.on("mouseenter", "hotspots", (e: MapLayerMouseEvent) => {
      m.getCanvas().style.cursor = "pointer";
      const f = e.features?.[0];
      if (f) popup.setLngLat(e.lngLat).setHTML(`<strong>${String(f.properties?.name ?? "")}</strong>`).addTo(m);
    });
    m.on("mouseleave", "hotspots", () => {
      m.getCanvas().style.cursor = "";
      popup.remove();
    });
    map.current = m;
    return () => {
      ready.current = false;
      m.remove();
      map.current = null;
    };
  }, []);

  // push data into sources whenever props change (after the style has loaded)
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const apply = () => {
      const roadData = roads && hideGreen ? fc(roads.features.filter((f) => f.properties?.a !== "green")) : roads;
      (m.getSource("roads") as GeoJSONSource | undefined)?.setData(roadData ?? EMPTY);
      (m.getSource("hotspots") as GeoJSONSource | undefined)?.setData(
        fc((hotspots ?? []).map((h) => pt(h.lon, h.lat, { name: h.name, a: h.alert }))),
      );
      (m.getSource("reports") as GeoJSONSource | undefined)?.setData(
        fc((reports ?? []).map((r) => pt(r.lon, r.lat, { c: r.category }))),
      );
      (m.getSource("zones") as GeoJSONSource | undefined)?.setData(
        fc((zones ?? []).map((z) => pt(z.lon, z.lat, { rank: String(z.rank) }))),
      );
      (m.getSource("picked") as GeoJSONSource | undefined)?.setData(picked ? fc([pt(picked.lon, picked.lat, {})]) : EMPTY);
    };
    if (ready.current) apply();
    else pending.current = apply;
  }, [roads, hotspots, reports, zones, picked, hideGreen]);

  useEffect(() => {
    if (flyTo && map.current) map.current.flyTo({ center: [flyTo.lon, flyTo.lat], zoom: flyTo.zoom ?? 15, speed: 1.4 });
  }, [flyTo]);

  return <div ref={el} className={className ?? "h-full w-full"} role="application" aria-label="Map of street alerts" />;
}
