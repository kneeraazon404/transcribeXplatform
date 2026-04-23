"use client";

import { useEffect, useRef } from "react";

interface Props {
  filename: string | null;
  messages: string[];
  provider?: string;
}

export default function ProgressView({ filename, messages, provider }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="w-full space-y-4">
      <div className="flex items-center gap-3">
        <div className="w-5 h-5 rounded-full border-2 border-neutral-700 border-t-violet-500 animate-spin flex-shrink-0" />
        <span className="text-neutral-300 font-medium truncate">
          {filename ?? "Transcribing…"}
          {provider && (
            <span className="ml-2 text-xs text-neutral-500 font-normal">via {provider}</span>
          )}
        </span>
      </div>

      <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-4 font-mono text-xs space-y-1.5 max-h-64 overflow-y-auto">
        {messages.length === 0 ? (
          <span className="text-neutral-600">Starting…</span>
        ) : (
          messages.map((msg, i) => (
            <div
              key={i}
              className={[
                "leading-relaxed",
                i === messages.length - 1 ? "text-violet-300" : "text-neutral-400",
              ].join(" ")}
            >
              <span className="text-neutral-600 select-none mr-2">›</span>
              {msg}
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
