"use client";

import dynamic from "next/dynamic";

// MapLibre touches `window`, so the map is rendered on the client only.
const RiskMap = dynamic(() => import("./RiskMap"), {
  ssr: false,
  loading: () => <div className="h-full w-full animate-pulse bg-zinc-100 dark:bg-zinc-900" />,
});

export default RiskMap;
