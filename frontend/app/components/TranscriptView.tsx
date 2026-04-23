"use client";

import { useCallback, useState } from "react";

interface Props {
  transcript: string;
  filename: string | null;
  onReset: () => void;
}

export default function TranscriptView({ transcript, filename, onReset }: Props) {
  const [copied, setCopied] = useState(false);

  const downloadMd = useCallback(() => {
    const stem = filename?.replace(/\.[^.]+$/, "") ?? "transcript";
    const blob = new Blob([transcript], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${stem}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }, [transcript, filename]);

  const downloadTxt = useCallback(() => {
    const stem = filename?.replace(/\.[^.]+$/, "") ?? "transcript";
    const blob = new Blob([transcript], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${stem}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }, [transcript, filename]);

  const copy = useCallback(() => {
    navigator.clipboard.writeText(transcript).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [transcript]);

  const lineCount = transcript.split("\n").filter((l) => l.trim()).length;

  return (
    <div className="w-full space-y-4">
      {/* Toolbar */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex-1 min-w-0">
          <h2 className="font-semibold truncate">{filename ?? "Transcript"}</h2>
          <p className="text-xs text-neutral-500">{lineCount} lines</p>
        </div>
        <button
          onClick={copy}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-sm transition-colors"
        >
          {copied ? (
            <>
              <CheckIcon className="w-4 h-4 text-green-400" />
              Copied
            </>
          ) : (
            <>
              <CopyIcon className="w-4 h-4" />
              Copy
            </>
          )}
        </button>
        <button
          onClick={downloadMd}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-sm transition-colors"
        >
          <DownloadIcon className="w-4 h-4" />
          .md
        </button>
        <button
          onClick={downloadTxt}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-sm transition-colors"
        >
          <DownloadIcon className="w-4 h-4" />
          .txt
        </button>
        <button
          onClick={onReset}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-violet-700 hover:bg-violet-600 text-sm transition-colors"
        >
          New file
        </button>
      </div>

      {/* Transcript content */}
      <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-5 font-mono text-sm leading-relaxed max-h-[60vh] overflow-y-auto whitespace-pre-wrap text-neutral-200">
        {transcript}
      </div>
    </div>
  );
}

function CopyIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.5} className={className}>
      <rect x="7" y="7" width="9" height="11" rx="1.5" />
      <path d="M13 7V5.5A1.5 1.5 0 0011.5 4h-7A1.5 1.5 0 003 5.5v9A1.5 1.5 0 004.5 16H7" />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={2} className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 10.5l4 4 7-7" />
    </svg>
  );
}

function DownloadIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.5} className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M10 3v10m0 0l-3.5-3.5M10 13l3.5-3.5M3 17h14" />
    </svg>
  );
}
