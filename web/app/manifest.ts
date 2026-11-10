import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Monsoon Sentinel — Pune rain & waterlogging alerts",
    short_name: "Monsoon Sentinel",
    description: "Explainable, street-level heavy-rain and waterlogging early warnings for Pune.",
    start_url: "/",
    display: "standalone",
    background_color: "#09090b",
    theme_color: "#0f766e",
    lang: "en-IN",
    icons: [{ src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" }],
  };
}
