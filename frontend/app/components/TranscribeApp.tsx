"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import LogoMark from "./LogoMark";
import DropZone from "./DropZone";
import ProgressView from "./ProgressView";
import TranscriptView from "./TranscriptView";

// ---------------------------------------------------------------------------
// Provider metadata
// ---------------------------------------------------------------------------

type BackendKey = "assemblyai" | "openai" | "deepgram" | "whisper";
type Tier = "free" | "freemium" | "paid";
type AppState = "idle" | "uploading" | "processing" | "done" | "error";

interface Provider {
  key: BackendKey;
  name: string;
  tier: Tier;
  tagline: string;
  pricing: string;
  features: string[];
  diarization: boolean;
  defaultModel: string;
  models: { value: string; label: string }[];
}

const PROVIDERS: Provider[] = [
  {
    key: "assemblyai",
    name: "AssemblyAI",
    tier: "freemium",
    tagline: "Best for multi-speaker meetings",
    pricing: "$0.17 / hr · $50 free credits",
    features: ["Speaker diarization", "Name detection", "99+ languages"],
    diarization: true,
    defaultModel: "",
    models: [], // single model, no selection
  },
  {
    key: "deepgram",
    name: "Deepgram Nova-3",
    tier: "freemium",
    tagline: "Fast, accurate, free tier available",
    pricing: "$0.0043 / min · 12 000 min/yr free",
    features: ["Speaker diarization", "40+ languages", "Fast processing"],
    diarization: true,
    defaultModel: "nova-3",
    models: [
      { value: "nova-3", label: "Nova-3 — latest, best quality" },
      { value: "nova-2", label: "Nova-2 — reliable" },
      { value: "enhanced", label: "Enhanced — general purpose" },
      { value: "base", label: "Base — budget tier" },
    ],
  },
  {
    key: "openai",
    name: "OpenAI Whisper",
    tier: "paid",
    tagline: "GPT-4o-powered, pay-per-minute",
    pricing: "$0.003–$0.006 / min · no free tier",
    features: ["99+ languages", "GPT-4o quality", "Fast"],
    diarization: false,
    defaultModel: "gpt-4o-mini-transcribe",
    models: [
      {
        value: "gpt-4o-mini-transcribe",
        label: "gpt-4o-mini — $0.003/min (fast)",
      },
      {
        value: "gpt-4o-transcribe",
        label: "gpt-4o — $0.006/min (best quality)",
      },
      { value: "whisper-1", label: "whisper-1 — $0.006/min (classic)" },
    ],
  },
  {
    key: "whisper",
    name: "Whisper (Local)",
    tier: "free",
    tagline: "Runs on your machine, no API key",
    pricing: "Free forever · open source",
    features: ["Offline & private", "99+ languages", "No account needed"],
    diarization: false,
    defaultModel: "base",
    models: [
      { value: "tiny", label: "tiny — fastest, ~39 MB" },
      { value: "base", label: "base — balanced, ~74 MB (default)" },
      { value: "small", label: "small — better accuracy, ~244 MB" },
      { value: "medium", label: "medium — high accuracy, ~769 MB" },
      {
        value: "large-v3-turbo",
        label: "large-v3-turbo — best quality, ~1.5 GB",
      },
    ],
  },
];

const TIER_STYLES: Record<Tier, string> = {
  free: "bg-emerald-900/60 text-emerald-300 border-emerald-700",
  freemium: "bg-blue-900/60 text-blue-300 border-blue-700",
  paid: "bg-violet-900/60 text-violet-300 border-violet-700",
};

const TIER_LABELS: Record<Tier, string> = {
  free: "Free",
  freemium: "Freemium",
  paid: "Paid",
};

const CARD_STYLES: Record<BackendKey, { inactive: string; active: string }> = {
  assemblyai: {
    inactive:
      "border-indigo-900/60 bg-gradient-to-br from-indigo-950/35 via-slate-950 to-cyan-950/20 hover:border-indigo-500/70",
    active:
      "border-indigo-400 bg-gradient-to-br from-indigo-950/70 via-indigo-950/40 to-cyan-950/30 ring-1 ring-indigo-400/30",
  },
  deepgram: {
    inactive:
      "border-cyan-900/60 bg-gradient-to-br from-cyan-950/35 via-slate-950 to-teal-950/20 hover:border-cyan-500/70",
    active:
      "border-cyan-400 bg-gradient-to-br from-cyan-950/70 via-cyan-950/40 to-teal-950/30 ring-1 ring-cyan-400/30",
  },
  openai: {
    inactive:
      "border-emerald-900/60 bg-gradient-to-br from-emerald-950/35 via-slate-950 to-lime-950/20 hover:border-emerald-500/70",
    active:
      "border-emerald-400 bg-gradient-to-br from-emerald-950/70 via-emerald-950/40 to-lime-950/30 ring-1 ring-emerald-400/30",
  },
  whisper: {
    inactive:
      "border-orange-900/60 bg-gradient-to-br from-orange-950/35 via-slate-950 to-rose-950/20 hover:border-orange-500/70",
    active:
      "border-orange-400 bg-gradient-to-br from-orange-950/70 via-orange-950/40 to-rose-950/30 ring-1 ring-orange-400/30",
  },
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface BackendHealth {
  assemblyai: boolean;
  openai: boolean;
  deepgram: boolean;
  whisper: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function TranscribeApp() {
  const [appState, setAppState] = useState<AppState>("idle");
  const [selectedBackend, setSelectedBackend] =
    useState<BackendKey>("assemblyai");
  const [model, setModel] = useState("");
  const [language, setLanguage] = useState("");
  const [title, setTitle] = useState("");
  const [messages, setMessages] = useState<string[]>([]);
  const [transcript, setTranscript] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [health, setHealth] = useState<BackendHealth | null>(null);
  const [filename, setFilename] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  const provider = PROVIDERS.find((p) => p.key === selectedBackend)!;
  const apiBaseUrl =
    process.env.NODE_ENV === "production" ? "" : "http://localhost:8000";
  const apiUrl = useCallback(
    (path: string) => `${apiBaseUrl}${path}`,
    [apiBaseUrl],
  );
  const handleSelectBackend = useCallback((key: BackendKey) => {
    setSelectedBackend(key);
    setModel(PROVIDERS.find((p) => p.key === key)?.defaultModel ?? "");
  }, []);

  // Fetch backend availability on mount
  useEffect(() => {
    fetch(apiUrl("/api/health"))
      .then((r) => r.json())
      .then((d) => setHealth(d.backends))
      .catch(() => {});
  }, [apiUrl]);

  const reset = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
    setAppState("idle");
    setMessages([]);
    setTranscript(null);
    setErrorMsg(null);
    setFilename(null);
  }, []);

  const handleFile = useCallback(
    async (file: File) => {
      setFilename(file.name);
      setMessages([]);
      setTranscript(null);
      setErrorMsg(null);
      setAppState("uploading");

      const fd = new FormData();
      fd.append("file", file);
      fd.append("backend", selectedBackend);
      fd.append("model", model || provider.defaultModel);
      fd.append("language", language);
      fd.append("title", title || file.name.replace(/\.[^.]+$/, ""));

      let jobId: string;
      try {
        const res = await fetch(apiUrl("/api/transcribe"), {
          method: "POST",
          body: fd,
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail ?? "Upload failed");
        }
        jobId = (await res.json()).job_id;
      } catch (e: unknown) {
        setErrorMsg(e instanceof Error ? e.message : String(e));
        setAppState("error");
        return;
      }

      setAppState("processing");

      const es = new EventSource(apiUrl(`/api/jobs/${jobId}/events`));
      esRef.current = es;

      es.onmessage = (evt) => {
        const payload = JSON.parse(evt.data);
        if (payload.type === "message") {
          setMessages((prev) => [...prev, payload.text]);
        } else if (payload.type === "done") {
          es.close();
          esRef.current = null;
          if (payload.status === "completed") {
            fetch(apiUrl(`/api/jobs/${jobId}/transcript`))
              .then((r) => r.json())
              .then((d) => {
                setTranscript(d.transcript);
                setAppState("done");
              })
              .catch((e) => {
                setErrorMsg(String(e));
                setAppState("error");
              });
          } else {
            setErrorMsg(payload.error ?? "Transcription failed");
            setAppState("error");
          }
        }
      };

      es.onerror = () => {
        es.close();
        esRef.current = null;
        setErrorMsg("Connection to server was lost");
        setAppState("error");
      };
    },
    [apiUrl, selectedBackend, model, language, title, provider.defaultModel],
  );

  return (
    <div className="min-h-screen bg-grid text-neutral-100 flex flex-col">
      {/* Header */}
      <header className="border-b border-neutral-700/80 bg-neutral-950/92 backdrop-blur sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-5 flex items-center gap-4">
          <div className="shrink-0 rounded-2xl border border-white/15 bg-linear-to-br from-cyan-500/12 via-indigo-500/10 to-orange-500/12 p-1.5 shadow-[0_0_0_1px_rgba(255,255,255,0.04),0_12px_30px_rgba(2,6,23,0.35)]">
            <LogoMark className="h-10 w-30 sm:h-11 sm:w-33" />
          </div>
          <div className="leading-tight">
            <span className="block font-semibold text-lg sm:text-xl tracking-tight">
              Transcribe
            </span>
            <span className="block text-xs sm:text-sm text-neutral-400">
              Audio & video to text
            </span>
          </div>
          {appState !== "idle" && (
            <button
              onClick={reset}
              className="ml-auto rounded-md px-2 py-1 text-sm text-neutral-300 transition-colors hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950"
            >
              ← New file
            </button>
          )}
        </div>
      </header>

      <main className="flex-1 flex flex-col items-center px-6 py-12 gap-10 max-w-7xl mx-auto w-full">
        {appState === "idle" && (
          <>
            <div className="w-full max-w-2xl mx-auto text-center sm:text-left">
              <h1 className="text-2xl sm:text-3xl lg:text-4xl xl:text-5xl font-bold tracking-tight text-balance mb-3">
                Audio & Video Transcription
              </h1>
              <p className="text-sm sm:text-base lg:text-lg leading-relaxed text-neutral-300 text-balance max-w-xl mx-auto sm:mx-0">
                Choose a provider, drop your file, get a speaker-labelled
                Markdown transcript.
              </p>
            </div>

            {/* Provider cards */}
            <ProviderSelector
              providers={PROVIDERS}
              selected={selectedBackend}
              health={health}
              onSelect={handleSelectBackend}
            />

            {/* Model selector (only for providers that have it) */}
            {provider.models.length > 0 && (
              <div className="w-full flex flex-col gap-2">
                <label className="text-sm font-medium text-neutral-300 uppercase tracking-wide">
                  {provider.name} model
                </label>
                <select
                  value={model || provider.defaultModel}
                  onChange={(e) => setModel(e.target.value)}
                  className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-4 py-3 text-base text-neutral-100 focus:outline-none focus:border-cyan-400 focus-visible:ring-2 focus-visible:ring-cyan-400/40"
                >
                  {provider.models.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Optional fields */}
            <div className="w-full grid grid-cols-2 gap-4">
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-neutral-300 uppercase tracking-wide">
                  Language
                </label>
                <input
                  type="text"
                  placeholder="Auto-detect (e.g. en, es, fr)"
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  className="bg-neutral-900 border border-neutral-700 rounded-lg px-4 py-3 text-base text-neutral-100 placeholder:text-neutral-500 focus:outline-none focus:border-cyan-400 focus-visible:ring-2 focus-visible:ring-cyan-400/40"
                />
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-neutral-300 uppercase tracking-wide">
                  Title
                </label>
                <input
                  type="text"
                  placeholder="Transcript title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="bg-neutral-900 border border-neutral-700 rounded-lg px-4 py-3 text-base text-neutral-100 placeholder:text-neutral-500 focus:outline-none focus:border-cyan-400 focus-visible:ring-2 focus-visible:ring-cyan-400/40"
                />
              </div>
            </div>

            <DropZone onFile={handleFile} />
          </>
        )}

        {appState === "uploading" && (
          <div
            className="w-full flex flex-col items-center gap-4 py-20"
            aria-live="polite"
            aria-busy="true"
          >
            <Spinner />
            <p className="text-neutral-300">Uploading {filename}…</p>
          </div>
        )}

        {appState === "processing" && (
          <ProgressView
            filename={filename}
            messages={messages}
            provider={provider.name}
          />
        )}

        {appState === "done" && transcript && (
          <TranscriptView
            transcript={transcript}
            filename={filename}
            onReset={reset}
          />
        )}

        {appState === "error" && (
          <div
            className="w-full bg-red-950/60 border border-red-700 rounded-xl p-6 space-y-3"
            role="alert"
          >
            <h2 className="font-semibold text-red-300">Transcription failed</h2>
            <pre className="text-sm text-red-200 font-mono whitespace-pre-wrap">
              {errorMsg}
            </pre>
            <button
              onClick={reset}
              className="mt-2 rounded-lg bg-neutral-800 px-4 py-2 text-sm transition-colors hover:bg-neutral-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-300 focus-visible:ring-offset-2 focus-visible:ring-offset-red-950"
            >
              Try again
            </button>
          </div>
        )}
      </main>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ProviderSelector
// ---------------------------------------------------------------------------

interface ProviderSelectorProps {
  providers: Provider[];
  selected: BackendKey;
  health: BackendHealth | null;
  onSelect: (key: BackendKey) => void;
}

function ProviderSelector({
  providers,
  selected,
  health,
  onSelect,
}: ProviderSelectorProps) {
  return (
    <div className="w-full space-y-3">
      <h2 className="text-sm font-semibold text-neutral-300 uppercase tracking-wide">
        Provider
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {providers.map((p) => {
          const available = health ? health[p.key] : true;
          const active = selected === p.key;
          return (
            <button
              key={p.key}
              onClick={() => onSelect(p.key)}
              className={[
                "relative overflow-hidden text-left rounded-xl border p-6 transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/50 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950",
                active
                  ? CARD_STYLES[p.key].active
                  : CARD_STYLES[p.key].inactive,
                !available && "opacity-50",
              ].join(" ")}
            >
              <div
                className={[
                  "absolute inset-x-0 top-0 h-1",
                  p.key === "assemblyai" &&
                    "bg-linear-to-r from-indigo-400 via-sky-400 to-cyan-300",
                  p.key === "deepgram" &&
                    "bg-linear-to-r from-cyan-400 via-teal-400 to-emerald-300",
                  p.key === "openai" &&
                    "bg-linear-to-r from-emerald-400 via-lime-400 to-amber-300",
                  p.key === "whisper" &&
                    "bg-linear-to-r from-orange-400 via-amber-400 to-rose-400",
                ]
                  .filter(Boolean)
                  .join(" ")}
              />
              {/* Header row */}
              <div className="flex items-start justify-between gap-2 mb-3">
                <span className="font-semibold text-base leading-tight text-neutral-100">
                  {p.name}
                </span>
                <span
                  className={`shrink-0 text-[11px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded border ${TIER_STYLES[p.tier]}`}
                >
                  {TIER_LABELS[p.tier]}
                </span>
              </div>

              {/* Tagline */}
              <p className="text-sm text-neutral-300 mb-3">{p.tagline}</p>

              {/* Features */}
              <ul className="space-y-1 mb-4">
                {p.features.map((f) => (
                  <li
                    key={f}
                    className="flex items-center gap-2 text-sm text-neutral-200"
                  >
                    <CheckSmallIcon className="w-4 h-4 text-emerald-500 shrink-0" />
                    {f}
                  </li>
                ))}
                {!p.diarization && (
                  <li className="flex items-center gap-2 text-sm text-neutral-400">
                    <XSmallIcon className="w-4 h-4 shrink-0" />
                    No speaker diarization
                  </li>
                )}
              </ul>

              {/* Pricing */}
              <p className="text-sm text-neutral-300 font-mono">{p.pricing}</p>

              {/* Unavailable badge */}
              {health && !available && (
                <div className="absolute top-3 right-3">
                  <span className="text-xs text-amber-200 bg-amber-950/70 border border-amber-600 rounded px-2 py-0.5">
                    {p.key === "whisper" ? "Not installed" : "No API key"}
                  </span>
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Spinner
// ---------------------------------------------------------------------------

function Spinner() {
  return (
    <div className="w-10 h-10 rounded-full border-2 border-neutral-700 border-t-violet-500 animate-spin" />
  );
}

function CheckSmallIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      className={className}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3 8l3.5 3.5 6.5-7"
      />
    </svg>
  );
}

function XSmallIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      className={className}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M4 4l8 8M12 4l-8 8"
      />
    </svg>
  );
}
