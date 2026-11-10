"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSentinel } from "@/lib/store";
import type { Lang } from "@/lib/types";

const LANGS: { id: Lang; label: string }[] = [
  { id: "en", label: "EN" },
  { id: "mr", label: "मराठी" },
  { id: "hi", label: "हिंदी" },
];

export function Logo({ className = "h-8 w-8" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <defs>
        <linearGradient id="ms-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#2563eb" />
          <stop offset="1" stopColor="#0f766e" />
        </linearGradient>
      </defs>
      <path d="M16 2.5c5 6.5 9.5 11.7 9.5 17a9.5 9.5 0 0 1-19 0c0-5.3 4.5-10.5 9.5-17z" fill="url(#ms-g)" />
      <path d="M11 20.5c1.6 1.4 3.2 2 5 2s3.4-.6 5-2" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" />
      <circle cx="16" cy="15.5" r="2.2" fill="#fff" />
    </svg>
  );
}

export default function TopBar() {
  const { t, lang, setLang, mode, date, setLive, setReplay, replayDays } = useSentinel();
  const path = usePathname();
  const nav = [
    { href: "/", label: t("citizen") },
    { href: "/control", label: t("control") },
    { href: "/about", label: t("howItWorks") },
  ];
  return (
    <header className="z-20 flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-zinc-200/80 bg-white/90 px-4 py-2.5 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/90">
      <Link href="/" className="flex items-center gap-2" aria-label={t("app")}>
        <Logo />
        <div className="leading-tight">
          <div className="text-[15px] font-bold tracking-tight">{t("app")}</div>
          <div className="hidden text-[11px] text-zinc-500 sm:block">{t("tagline")}</div>
        </div>
      </Link>

      <nav className="flex rounded-lg bg-zinc-100 p-0.5 text-sm dark:bg-zinc-800" aria-label="Views">
        {nav.map((n) => (
          <Link
            key={n.href}
            href={n.href + (date && n.href !== "/about" ? `?date=${date}` : "")}
            className={`rounded-md px-3 py-1 font-medium transition ${
              path === n.href ? "bg-white shadow-sm dark:bg-zinc-700" : "text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100"
            }`}
          >
            {n.label}
          </Link>
        ))}
      </nav>

      <div className="ml-auto flex flex-wrap items-center gap-2">
        <div className="flex items-center rounded-lg bg-zinc-100 p-0.5 text-sm dark:bg-zinc-800">
          <button
            onClick={setLive}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1 font-medium transition ${
              mode === "live" ? "bg-white shadow-sm dark:bg-zinc-700" : "text-zinc-500"
            }`}
          >
            <span className={`h-2 w-2 rounded-full ${mode === "live" ? "animate-pulse bg-emerald-500" : "bg-zinc-400"}`} />
            {t("live")}
          </button>
          <label className="sr-only" htmlFor="replay">{t("replay")}</label>
          <select
            id="replay"
            title={t("replayHint")}
            value={mode === "replay" ? (date ?? "") : ""}
            onChange={(e) => e.target.value && setReplay(e.target.value)}
            className={`max-w-[11rem] rounded-md bg-transparent px-2 py-1 font-medium outline-none sm:max-w-[16rem] ${
              mode === "replay" ? "bg-white shadow-sm dark:bg-zinc-700" : "text-zinc-500"
            }`}
          >
            <option value="">{t("replay")}…</option>
            {replayDays.map((d) => (
              <option key={d.date} value={d.date}>
                {d.date} · {d.label}
              </option>
            ))}
            {date && !replayDays.some((d) => d.date === date) && <option value={date}>{date}</option>}
          </select>
        </div>
        <select
          aria-label="Language"
          value={lang}
          onChange={(e) => setLang(e.target.value as Lang)}
          className="rounded-lg bg-zinc-100 px-2 py-1.5 text-sm font-medium outline-none sm:hidden dark:bg-zinc-800"
        >
          {LANGS.map((l) => (
            <option key={l.id} value={l.id}>{l.label}</option>
          ))}
        </select>
        <div className="hidden rounded-lg bg-zinc-100 p-0.5 text-sm sm:flex dark:bg-zinc-800" role="group" aria-label="Language">
          {LANGS.map((l) => (
            <button
              key={l.id}
              onClick={() => setLang(l.id)}
              aria-pressed={lang === l.id}
              className={`rounded-md px-2.5 py-1 font-medium transition ${
                lang === l.id ? "bg-white shadow-sm dark:bg-zinc-700" : "text-zinc-500"
              }`}
            >
              {l.label}
            </button>
          ))}
        </div>
      </div>
    </header>
  );
}
