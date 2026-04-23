import { useId } from "react";

interface LogoMarkProps {
  className?: string;
}

export default function LogoMark({ className }: LogoMarkProps) {
  const uid = useId();
  const baseId = `${uid}-base`;
  const chipId = `${uid}-chip`;
  const waveId = `${uid}-wave`;
  const shadowId = `${uid}-shadow`;

  return (
    <svg
      viewBox="0 0 900 300"
      fill="none"
      aria-hidden="true"
      focusable="false"
      className={className}
    >
      <defs>
        <linearGradient
          id={baseId}
          x1="36"
          y1="24"
          x2="864"
          y2="276"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0" stopColor="#0f172a" />
          <stop offset="0.36" stopColor="#1e1b4b" />
          <stop offset="0.72" stopColor="#0f766e" />
          <stop offset="1" stopColor="#0e7490" />
        </linearGradient>
        <linearGradient
          id={chipId}
          x1="90"
          y1="74"
          x2="812"
          y2="226"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0" stopColor="#22d3ee" />
          <stop offset="0.5" stopColor="#818cf8" />
          <stop offset="1" stopColor="#f97316" />
        </linearGradient>
        <linearGradient
          id={waveId}
          x1="302"
          y1="116"
          x2="602"
          y2="182"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0" stopColor="#f8fafc" />
          <stop offset="0.48" stopColor="#67e8f9" />
          <stop offset="1" stopColor="#c4b5fd" />
        </linearGradient>
        <filter
          id={shadowId}
          x="18"
          y="14"
          width="864"
          height="272"
          filterUnits="userSpaceOnUse"
        >
          <feDropShadow
            dx="0"
            dy="10"
            stdDeviation="16"
            floodColor="#020617"
            floodOpacity="0.34"
          />
        </filter>
      </defs>

      <rect
        x="24"
        y="24"
        width="852"
        height="252"
        rx="84"
        fill={`url(#${baseId})`}
      />
      <circle cx="748" cy="86" r="92" fill="#22d3ee" opacity="0.14" />
      <circle cx="194" cy="232" r="94" fill="#a855f7" opacity="0.1" />

      <g filter={`url(#${shadowId})`}>
        <path
          d="M86 66h728c29.8 0 54 24.2 54 54v60c0 29.8-24.2 54-54 54H86c-29.8 0-54-24.2-54-54v-60c0-29.8 24.2-54 54-54Z"
          fill="rgba(255,255,255,0.08)"
          stroke="rgba(255,255,255,0.18)"
          strokeWidth="2"
        />

        <rect
          x="112"
          y="95"
          width="110"
          height="110"
          rx="28"
          fill="rgba(15,23,42,0.38)"
          stroke="rgba(255,255,255,0.2)"
        />
        <rect x="126" y="108" width="16" height="46" rx="8" fill="#e2e8f0" />
        <rect x="120" y="152" width="28" height="10" rx="5" fill="#e2e8f0" />
        <path
          d="M134 164v14"
          stroke="#e2e8f0"
          strokeWidth="5"
          strokeLinecap="round"
        />
        <path
          d="M152 126c14 9 14 31 0 40"
          stroke="#67e8f9"
          strokeWidth="5"
          strokeLinecap="round"
        />
        <path
          d="M166 118c21 14 21 48 0 62"
          stroke="#22d3ee"
          strokeWidth="5"
          strokeLinecap="round"
        />

        <path
          d="M272 150c21-28 42-28 63 0s42 28 63 0 42-28 63 0 42 28 63 0 42-28 63 0"
          stroke={`url(#${waveId})`}
          strokeWidth="14"
          strokeLinecap="round"
        />

        <rect
          x="662"
          y="98"
          width="90"
          height="58"
          rx="14"
          fill="rgba(15,23,42,0.44)"
          stroke="rgba(255,255,255,0.24)"
        />
        <path
          d="M752 118l28-14v46l-28-14"
          fill="rgba(148,163,184,0.44)"
          stroke="rgba(248,250,252,0.64)"
          strokeWidth="2"
          strokeLinejoin="round"
        />

        <path
          d="M286 186h250"
          stroke="rgba(248,250,252,0.76)"
          strokeWidth="8"
          strokeLinecap="round"
        />
        <path
          d="M286 205h214"
          stroke="rgba(248,250,252,0.48)"
          strokeWidth="8"
          strokeLinecap="round"
        />
        <path
          d="M286 224h172"
          stroke="rgba(248,250,252,0.32)"
          strokeWidth="8"
          strokeLinecap="round"
        />

        <rect
          x="588"
          y="190"
          width="142"
          height="8"
          rx="4"
          fill="rgba(248,250,252,0.82)"
        />
        <rect
          x="588"
          y="205"
          width="104"
          height="8"
          rx="4"
          fill="rgba(248,250,252,0.5)"
        />
      </g>

      <rect
        x="570"
        y="174"
        width="248"
        height="48"
        rx="14"
        fill="rgba(255,255,255,0.03)"
        stroke={`url(#${chipId})`}
        strokeWidth="1.8"
      />
    </svg>
  );
}
