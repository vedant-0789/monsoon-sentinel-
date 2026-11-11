"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ALERT_COPY } from "@/lib/i18n";
import { floodProbability, downscale } from "@/lib/photo";
import { useSentinel } from "@/lib/store";
import type { Outlook } from "@/lib/types";
import { Card, Spinner } from "./ui";

/* ------------------------------------------------------------------ outlook */
export function OutlookChart({ o }: { o: Outlook }) {
  const hours = o.hours ?? [];
  if (!hours.length) return null;
  const W = 300;
  const H = 90;
  const pad = { l: 4, r: 4, t: 6, b: 14 };
  const iw = W - pad.l - pad.r;
  const ih = H - pad.t - pad.b;
  const maxV = Math.max(10, ...hours.map((h) => h.max));
  const bw = iw / hours.length;
  const y = (v: number) => pad.t + ih - (v / maxV) * ih;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img"
      aria-label={hours.map((h) => `${h.time.slice(11)} ${h.mean} mm`).join(", ")}>
      {hours.map((h, i) => {
        const x = pad.l + bw * i;
        const c = h.mean >= 10 ? "#c81e1e" : h.mean >= 4 ? "#f46d43" : "#60a5fa";
        return (
          <g key={h.time}>
            <rect x={x + bw * 0.42} y={y(h.max)} width={bw * 0.16} height={Math.max(y(h.min) - y(h.max), 0.5)}
              className="fill-zinc-400/50 dark:fill-zinc-500/50" />
            <rect x={x + bw * 0.15} y={y(h.mean)} width={bw * 0.7} height={Math.max(pad.t + ih - y(h.mean), 0.5)} rx="1" fill={c} opacity="0.9">
              <title>{`${h.time.slice(11)} IST · ${h.mean} mm (${h.min}–${h.max})\n${Object.entries(h.by_model).map(([k, v]) => `${k} ${v ?? "–"}`).join(" · ")}`}</title>
            </rect>
            {i % 6 === 0 && (
              <text x={x} y={H - 3} fontSize="8" className="fill-current opacity-60">{h.time.slice(11, 16)}</text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

export function OutlookCard({ compact = false }: { compact?: boolean }) {
  const { outlook: o, t } = useSentinel();
  if (!o) return null;
  return (
    <Card className={compact ? "!p-3" : ""}>
      <h2 className="text-sm font-semibold">{t("next24")}</h2>
      {!o.available ? (
        <p className="mt-1 text-xs text-zinc-500">{t("outlookUnavailable")}</p>
      ) : (
        <>
          <div className={`mt-2 rounded-xl px-3 py-2 text-xs ${o.intense_watch
            ? "bg-red-600 font-semibold text-white" : "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300"}`}
            role={o.intense_watch ? "alert" : undefined}>
            {o.intense_watch ? t("intenseWatch", { n: o.models_intense ?? 0, m: o.models?.length ?? 5 }) : t("noIntense")}
          </div>
          <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
            <div className="rounded-lg bg-zinc-100 px-2 py-1.5 dark:bg-zinc-800">
              <div className="text-zinc-500">{t("total24")}</div>
              <div className="font-semibold tabular-nums">{o.total_24h_mm?.mean} mm <span className="font-normal text-zinc-500">({o.total_24h_mm?.min}–{o.total_24h_mm?.max})</span></div>
            </div>
            <div className="rounded-lg bg-zinc-100 px-2 py-1.5 dark:bg-zinc-800">
              <div className="text-zinc-500">{t("peakAt")}</div>
              <div className="font-semibold tabular-nums">{o.peak_hour_ist?.slice(11, 16)} IST</div>
            </div>
          </div>
          <div className="mt-2"><OutlookChart o={o} /></div>
          <p className="mt-1 text-[10px] leading-snug text-zinc-500">{t("outlookNote")} · {o.models?.join(", ")}</p>
        </>
      )}
    </Card>
  );
}

/* ------------------------------------------------------------- photo picker */
export interface PhotoState {
  dataUrl: string;
  prob: number | null;
  checking: boolean;
}

export function PhotoPicker({ value, onChange }: { value: PhotoState | null; onChange: (p: PhotoState | null) => void }) {
  const { t } = useSentinel();
  const [err, setErr] = useState<string | null>(null);
  const pickFile = async (f: File | undefined) => {
    if (!f) return;
    setErr(null);
    try {
      const { dataUrl, img } = await downscale(f);
      onChange({ dataUrl, prob: null, checking: true });
      const prob = await floodProbability(img).catch(() => null);
      onChange({ dataUrl, prob, checking: false });
    } catch (e) {
      setErr((e as Error).message);
    }
  };
  const verdict = (p: number) =>
    p >= 0.7 ? { k: "photoFlood", c: "bg-emerald-600 text-white" }
      : p < 0.5 ? { k: "photoNoFlood", c: "bg-zinc-600 text-white" }
        : { k: "photoUnsure", c: "bg-amber-500 text-zinc-900" };
  return (
    <div className="mt-4">
      {!value ? (
        <label className="flex cursor-pointer items-center justify-center gap-2 rounded-xl border-2 border-dashed border-zinc-300 px-4 py-3 text-sm font-medium text-zinc-600 transition hover:border-blue-500 hover:text-blue-600 dark:border-zinc-700 dark:text-zinc-300">
          <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden>
            <path d="M4 7h3l2-3h6l2 3h3v12H4z" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
            <circle cx="12" cy="13" r="3.5" fill="none" stroke="currentColor" strokeWidth="2" />
          </svg>
          {t("addPhoto")}
          <input type="file" accept="image/*" capture="environment" className="sr-only"
            onChange={(e) => pickFile(e.target.files?.[0])} />
        </label>
      ) : (
        <div className="flex gap-3 rounded-xl border border-zinc-200 p-2 dark:border-zinc-800">
          {/* eslint-disable-next-line @next/next/no-img-element -- local data URL preview */}
          <img src={value.dataUrl} alt="" className="h-20 w-20 rounded-lg object-cover" />
          <div className="min-w-0 flex-1 space-y-1.5">
            {value.checking ? (
              <span className="flex items-center gap-2 text-xs text-zinc-500"><Spinner className="h-3.5 w-3.5" />{t("photoChecking")}</span>
            ) : value.prob !== null ? (
              (() => {
                const v = verdict(value.prob);
                return <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${v.c}`}>{t(v.k, { p: Math.round(value.prob * 100) })}</span>;
              })()
            ) : null}
            <p className="text-[11px] leading-snug text-zinc-500">{t("photoPrivacy")}</p>
            <button onClick={() => onChange(null)} className="text-xs text-zinc-500 underline">{t("removePhoto")}</button>
          </div>
        </div>
      )}
      {err && <p className="mt-1 text-xs text-red-600">{err}</p>}
    </div>
  );
}

/* --------------------------------------------------------- alert subscription */
export function SubscribeCard({ onOpen }: { onOpen: () => void }) {
  const { t } = useSentinel();
  return (
    <button onClick={onOpen}
      className="flex w-full items-center gap-3 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-left shadow-sm transition hover:border-emerald-400 dark:border-emerald-900 dark:bg-emerald-950/40">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-white" aria-hidden>
        <svg viewBox="0 0 24 24" className="h-5 w-5"><path d="M12 3a6 6 0 0 0-6 6v4l-2 3h16l-2-3V9a6 6 0 0 0-6-6zM9.5 19a2.5 2.5 0 0 0 5 0" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" /></svg>
      </span>
      <span className="min-w-0">
        <span className="block font-semibold text-emerald-900 dark:text-emerald-200">{t("getAlerts")}</span>
        <span className="block text-xs text-emerald-800/80 dark:text-emerald-300/80">{t("getAlertsSub")}</span>
      </span>
    </button>
  );
}

export function SubscribeSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t, lang, picked, alertLabels } = useSentinelWithLabels();
  const [channel, setChannel] = useState<"whatsapp" | "sms">("whatsapp");
  const [phoneInput, setPhoneInput] = useState("");
  // a 10-digit Indian mobile gets +91; anything typed with + is used as given (E.164)
  const digits = phoneInput.replace(/[\s-]/g, "");
  const phone = digits.startsWith("+") ? digits : `+91${digits.replace(/^0/, "")}`;
  const [label, setLabel] = useState("");
  const [minAlert, setMinAlert] = useState<"yellow" | "orange" | "red">("orange");
  const [consent, setConsent] = useState(false);
  const [step, setStep] = useState<"form" | "code" | "done">("form");
  const [subId, setSubId] = useState<number | null>(null);
  const [demo, setDemo] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;

  const place = picked?.info?.nearest_road?.replace(/^Near /, "") ?? "";
  const start = async () => {
    if (!picked) return;
    setBusy(true);
    setErr(null);
    try {
      const r = await api.subscribe({ channel, phone, lang, lat: picked.lat, lon: picked.lon,
        label: (label || place || "My street").slice(0, 60), min_alert: minAlert, consent });
      setSubId(r.id);
      setDemo(r.demo_code ?? null);
      setStep("code");
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const confirm = async () => {
    if (subId === null) return;
    setBusy(true);
    setErr(null);
    try {
      await api.verifySubscription(subId, code.trim());
      setStep("done");
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const seg = (on: boolean) => `flex-1 rounded-lg px-3 py-2 text-sm font-medium transition ${on ? "bg-white shadow-sm dark:bg-zinc-700" : "text-zinc-500"}`;
  const input = "mt-1 w-full rounded-xl border border-zinc-300 bg-transparent px-3 py-2 text-sm outline-none focus:border-blue-600 dark:border-zinc-700";
  const phoneOk = /^\+[1-9]\d{7,14}$/.test(phone) && (digits.startsWith("+") || /^0?[6-9]\d{9}$/.test(digits));

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-labelledby="sub-title"
        className="max-h-[92vh] w-full max-w-md overflow-y-auto rounded-t-3xl bg-white p-5 shadow-2xl sm:rounded-3xl dark:bg-zinc-900"
        onClick={(e) => e.stopPropagation()}>
        <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-zinc-300 sm:hidden" />
        <h2 id="sub-title" className="text-lg font-bold">{t("subTitle")}</h2>
        {!picked ? (
          <p className="mt-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">{t("pickPlaceFirst")}</p>
        ) : step === "form" ? (
          <div className="mt-3 space-y-3">
            <div>
              <div className="text-sm font-medium">{t("channel")}</div>
              <div className="mt-1 flex rounded-xl bg-zinc-100 p-1 dark:bg-zinc-800">
                <button className={seg(channel === "whatsapp")} onClick={() => setChannel("whatsapp")} aria-pressed={channel === "whatsapp"}>WhatsApp</button>
                <button className={seg(channel === "sms")} onClick={() => setChannel("sms")} aria-pressed={channel === "sms"}>SMS</button>
              </div>
            </div>
            <label className="block text-sm font-medium">{t("phone")}
              <div className="mt-1 flex items-center rounded-xl border border-zinc-300 focus-within:border-blue-600 dark:border-zinc-700">
                {!digits.startsWith("+") && <span className="pl-3 text-sm text-zinc-500">+91</span>}
                <input className="w-full bg-transparent px-2 py-2 text-sm outline-none" inputMode="tel" autoComplete="tel-national"
                  value={phoneInput} onChange={(e) => setPhoneInput(e.target.value)} placeholder="98XXXXXXXX" />
              </div>
            </label>
            <label className="block text-sm font-medium">{t("placeName")}
              <input className={input} value={label} maxLength={60} onChange={(e) => setLabel(e.target.value)} placeholder={place || "Home"} />
            </label>
            <div>
              <div className="text-sm font-medium">{t("alertFrom")}</div>
              <div className="mt-1 flex rounded-xl bg-zinc-100 p-1 dark:bg-zinc-800">
                {(["yellow", "orange", "red"] as const).map((a) => (
                  <button key={a} className={seg(minAlert === a)} onClick={() => setMinAlert(a)} aria-pressed={minAlert === a}>{alertLabels[a]}</button>
                ))}
              </div>
            </div>
            <label className="flex items-start gap-2 text-xs leading-snug">
              <input type="checkbox" className="mt-0.5" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
              {t("consent")}
            </label>
            {err && <p className="text-sm text-red-600">{err}</p>}
            <button onClick={start} disabled={!consent || !phoneOk || busy}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-3 text-sm font-semibold text-white disabled:opacity-40">
              {busy && <Spinner />}{t("sendCode")}
            </button>
          </div>
        ) : step === "code" ? (
          <div className="mt-3 space-y-3">
            {demo && <p className="rounded-xl bg-sky-50 p-3 text-sm text-sky-900 dark:bg-sky-950/40 dark:text-sky-200">{t("demoCode", { c: demo })}</p>}
            <label className="block text-sm font-medium">{t("enterCode")}
              <input className={`${input} text-center text-2xl tracking-[0.5em]`} inputMode="numeric" autoComplete="one-time-code"
                maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} />
            </label>
            {err && <p className="text-sm text-red-600">{err}</p>}
            <button onClick={confirm} disabled={code.length !== 6 || busy}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-3 text-sm font-semibold text-white disabled:opacity-40">
              {busy && <Spinner />}{t("verify")}
            </button>
          </div>
        ) : (
          <p className="mt-3 rounded-xl bg-emerald-50 p-4 text-sm text-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200">
            {t("subscribed", { l: label || place || "My street" })}
          </p>
        )}
        <button onClick={onClose} className="mt-4 w-full rounded-xl border border-zinc-300 px-4 py-2.5 text-sm font-medium dark:border-zinc-700">{t("close")}</button>
      </div>
    </div>
  );
}

function useSentinelWithLabels() {
  const s = useSentinel();
  const c = ALERT_COPY[s.lang];
  return { ...s, alertLabels: { yellow: c.yellow.title, orange: c.orange.title, red: c.red.title } };
}
