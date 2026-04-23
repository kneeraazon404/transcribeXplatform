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

  // Fetch backend availability on mount
  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then((d) => setHealth(d.backends))
      .catch(() => {});
  }, []);

  // Reset model when backend changes
  useEffect(() => {
    setModel(provider.defaultModel);
  }, [selectedBackend, provider.defaultModel]);

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
        const res = await fetch("/api/transcribe", {
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

      const es = new EventSource(`/api/jobs/${jobId}/events`);
      esRef.current = es;

      es.onmessage = (evt) => {
        const payload = JSON.parse(evt.data);
        if (payload.type === "message") {
          setMessages((prev) => [...prev, payload.text]);
        } else if (payload.type === "done") {
          es.close();
          esRef.current = null;
          if (payload.status === "completed") {
            fetch(`/api/jobs/${jobId}/transcript`)
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
    [selectedBackend, model, language, title, provider.defaultModel],
  );

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex flex-col">
      {/* Header */}
      <header className="border-b border-neutral-800/80 bg-neutral-950/85 backdrop-blur px-6 py-4 flex items-center gap-3">
        <LogoMark className="h-10 w-10 shrink-0" />
        <div className="leading-tight">
          <span className="block font-semibold text-lg tracking-tight">
            Transcribe
          </span>
          <span className="block text-xs text-neutral-500">
            Audio & video to text
          </span>
        </div>
        {appState !== "idle" && (
          <button
            onClick={reset}
            className="ml-auto text-sm text-neutral-400 hover:text-white transition-colors"
          >
            ← New file
          </button>
        )}
      </header>

      <main className="flex-1 flex flex-col items-center px-4 py-10 gap-8 max-w-3xl mx-auto w-full">
        {appState === "idle" && (
          <>
            <div className="w-full flex items-center gap-4">
              <LogoMark className="h-14 w-14 shrink-0" />
              <div>
                <h1 className="text-2xl font-bold mb-1">
                  Audio & Video Transcription
                </h1>
                <p className="text-neutral-400 text-sm">
                  Choose a provider, drop your file, get a speaker-labelled
                  Markdown transcript.
                </p>
              </div>
            </div>

            {/* Provider cards */}
            <ProviderSelector
              providers={PROVIDERS}
              selected={selectedBackend}
              health={health}
              onSelect={setSelectedBackend}
            />

            {/* Model selector (only for providers that have it) */}
            {provider.models.length > 0 && (
              <div className="w-full flex flex-col gap-1.5">
                <label className="text-xs font-medium text-neutral-400 uppercase tracking-wide">
                  {provider.name} model
                </label>
                <select
                  value={model || provider.defaultModel}
                  onChange={(e) => setModel(e.target.value)}
                  className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-violet-500"
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
            <div className="w-full grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-neutral-400 uppercase tracking-wide">
                  Language
                </label>
                <input
                  type="text"
                  placeholder="Auto-detect (e.g. en, es, fr)"
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  className="bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-violet-500 placeholder-neutral-600"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-neutral-400 uppercase tracking-wide">
                  Title
                </label>
                <input
                  type="text"
                  placeholder="Transcript title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-violet-500 placeholder-neutral-600"
                />
              </div>
            </div>

            <DropZone onFile={handleFile} />
          </>
        )}

        {appState === "uploading" && (
          <div className="w-full flex flex-col items-center gap-4 py-20">
            <Spinner />
            <p className="text-neutral-400">Uploading {filename}…</p>
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
          <div className="w-full bg-red-950/60 border border-red-800 rounded-xl p-6 space-y-3">
            <h2 className="font-semibold text-red-300">Transcription failed</h2>
            <pre className="text-sm text-red-400 font-mono whitespace-pre-wrap">
              {errorMsg}
            </pre>
            <button
              onClick={reset}
              className="mt-2 px-4 py-2 bg-neutral-800 hover:bg-neutral-700 rounded-lg text-sm transition-colors"
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
    <div className="w-full space-y-2">
      <h2 className="text-xs font-semibold text-neutral-400 uppercase tracking-wide">
        Provider
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {providers.map((p) => {
          const available = health ? health[p.key] : true;
          const active = selected === p.key;
          return (
            <button
              key={p.key}
              onClick={() => onSelect(p.key)}
              className={[
                "relative text-left rounded-xl border p-4 transition-all focus:outline-none",
                active
                  ? "border-violet-500 bg-violet-950/40 ring-1 ring-violet-500/30"
                  : "border-neutral-800 bg-neutral-900 hover:border-neutral-600",
                !available && "opacity-50",
              ].join(" ")}
            >
              {/* Header row */}
              <div className="flex items-start justify-between gap-2 mb-2">
                <span className="font-semibold text-sm leading-tight">
                  {p.name}
                </span>
                <span
                  className={`shrink-0 text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded border ${TIER_STYLES[p.tier]}`}
                >
                  {TIER_LABELS[p.tier]}
                </span>
              </div>

              {/* Tagline */}
              <p className="text-xs text-neutral-400 mb-2">{p.tagline}</p>

              {/* Features */}
              <ul className="space-y-0.5 mb-3">
                {p.features.map((f) => (
                  <li
                    key={f}
                    className="flex items-center gap-1.5 text-xs text-neutral-300"
                  >
                    <CheckSmallIcon className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                    {f}
                  </li>
                ))}
                {!p.diarization && (
                  <li className="flex items-center gap-1.5 text-xs text-neutral-500">
                    <XSmallIcon className="w-3.5 h-3.5 shrink-0" />
                    No speaker diarization
                  </li>
                )}
              </ul>

              {/* Pricing */}
              <p className="text-xs text-neutral-500 font-mono">{p.pricing}</p>

              {/* Unavailable badge */}
              {health && !available && (
                <div className="absolute top-2 right-2">
                  <span className="text-[10px] text-amber-400 bg-amber-950/60 border border-amber-700 rounded px-1.5 py-0.5">
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
