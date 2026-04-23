import { useId } from "react";

interface LogoMarkProps {
  className?: string;
}

export default function LogoMark({ className }: LogoMarkProps) {
  const uid = useId();
  const bgId = `${uid}-bg`;
  const accentId = `${uid}-accent`;
  const shadowId = `${uid}-shadow`;

  return (
    <svg
      viewBox="0 0 512 512"
      fill="none"
      aria-hidden="true"
      focusable="false"
      className={className}
    >
      <defs>
        <linearGradient
          id={bgId}
          x1="72"
          y1="72"
          x2="440"
          y2="440"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0" stopColor="#0f172a" />
          <stop offset="0.55" stopColor="#1e1b4b" />
          <stop offset="1" stopColor="#0f766e" />
        </linearGradient>
        <linearGradient
          id={accentId}
          x1="160"
          y1="196"
          x2="360"
          y2="320"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0" stopColor="#38bdf8" />
          <stop offset="0.45" stopColor="#8b5cf6" />
          <stop offset="1" stopColor="#34d399" />
        </linearGradient>
        <filter
          id={shadowId}
          x="52"
          y="52"
          width="408"
          height="408"
          filterUnits="userSpaceOnUse"
        >
          <feDropShadow
            dx="0"
            dy="10"
            stdDeviation="18"
            floodColor="#020617"
            floodOpacity="0.38"
          />
        </filter>
      </defs>

      <rect
        x="48"
        y="48"
        width="416"
        height="416"
        rx="124"
        fill={`url(#${bgId})`}
      />
      <circle cx="374" cy="122" r="108" fill="#38bdf8" opacity="0.14" />

      <g filter={`url(#${shadowId})`}>
        <path
          d="M160 146h192c31.5 0 57 25.5 57 57v66c0 31.5-25.5 57-57 57h-71l-56 54v-54h-65c-31.5 0-57-25.5-57-57v-66c0-31.5 25.5-57 57-57Z"
          fill="rgba(255,255,255,0.07)"
          stroke="rgba(255,255,255,0.16)"
          strokeWidth="2"
        />

        <path
          d="M188 220c14-18 29-18 43 0s29 18 43 0 29-18 43 0 29 18 43 0 29-18 43 0"
          stroke={`url(#${accentId})`}
          strokeWidth="18"
          strokeLinecap="round"
        />

        <rect
          x="188"
          y="260"
          width="138"
          height="12"
          rx="6"
          fill="#f8fafc"
          opacity="0.94"
        />
        <rect
          x="188"
          y="286"
          width="172"
          height="12"
          rx="6"
          fill="#f8fafc"
          opacity="0.64"
        />
        <rect
          x="188"
          y="312"
          width="118"
          height="12"
          rx="6"
          fill="#f8fafc"
          opacity="0.44"
        />
      </g>
    </svg>
  );
}
