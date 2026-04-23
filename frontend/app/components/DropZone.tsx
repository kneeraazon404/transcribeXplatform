"use client";

import { useCallback, useRef, useState } from "react";

const ACCEPTED = [
  "audio/wav",
  "audio/mpeg",
  "audio/flac",
  "audio/ogg",
  "audio/aac",
  "audio/mp4",
  "audio/x-m4a",
  "audio/webm",
  "video/mp4",
  "video/quicktime",
  "video/x-msvideo",
  "video/x-matroska",
  "video/webm",
  "video/x-flv",
].join(",");

interface Props {
  onFile: (file: File) => void;
}

export default function DropZone({ onFile }: Props) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const triggerFilePicker = useCallback(() => {
    inputRef.current?.click();
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => setDragging(false), []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) onFile(file);
    },
    [onFile],
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) onFile(file);
    },
    [onFile],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        triggerFilePicker();
      }
    },
    [triggerFilePicker],
  );

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={triggerFilePicker}
      onKeyDown={handleKeyDown}
      role="button"
      tabIndex={0}
      aria-label="Upload audio or video file"
      className={[
        "w-full border-2 border-dashed rounded-xl p-12 flex flex-col items-center gap-4 cursor-pointer transition-all outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/40 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950",
        dragging
          ? "border-cyan-400 bg-cyan-950/25"
          : "border-neutral-600 hover:border-neutral-400 bg-neutral-900/60",
      ].join(" ")}
    >
      <div className="w-14 h-14 rounded-2xl bg-neutral-800/90 border border-neutral-700 flex items-center justify-center">
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.5}
          className="w-7 h-7 text-neutral-300"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
          />
        </svg>
      </div>
      <div className="text-center">
        <p className="font-medium">Drop your file here</p>
        <p className="text-neutral-400 text-sm mt-1">or click to browse</p>
      </div>
      <p className="text-xs text-neutral-500">
        MP3, MP4, WAV, M4A, FLAC, OGG, MOV, MKV, WebM and more
      </p>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED}
        onChange={handleChange}
        className="hidden"
      />
    </div>
  );
}
