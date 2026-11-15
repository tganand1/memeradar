"use client";

import { cn } from "@/lib/utils";

export function ScoreGauge({
  score,
  label,
  size = 132,
  thickness = 9,
  className,
}: {
  score: number;
  label?: string;
  size?: number;
  thickness?: number;
  className?: string;
}) {
  const value = Math.max(0, Math.min(100, Number(score) || 0));
  const radius = (size - thickness) / 2;
  const circumference = 2 * Math.PI * radius;
  const dash = (value / 100) * circumference;
  const color = value >= 74 ? "hsl(157, 90%, 60%)" : value >= 56 ? "hsl(38, 95%, 60%)" : "hsl(355, 85%, 62%)";

  return (
    <div className={cn("relative inline-flex items-center justify-center", className)} style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={thickness} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={thickness}
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circumference - dash}`}
          style={{ filter: `drop-shadow(0 0 8px ${color})` }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-mono text-2xl font-bold leading-none tracking-tight text-fg">{Math.round(value)}</span>
        <span className="mt-1 font-mono text-[9px] uppercase tracking-[0.18em] text-muted">{label || "Score"}</span>
      </div>
    </div>
  );
}
