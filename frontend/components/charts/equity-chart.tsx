"use client";

import { useId, useMemo } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from "recharts";

import { fmtClock, fmtDate, fmtUsd } from "@/lib/format";
import type { EquityPoint } from "@/lib/types";

function ChartTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: { t: number; equity: number; cash: number } }>;
}) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  const date = new Date(point.t);
  return (
    <div className="rounded-xl border border-white/10 bg-[#080d14]/95 px-3 py-2 shadow-xl backdrop-blur">
      <p className="font-mono text-[10px] uppercase tracking-wider text-muted">
        {fmtDate(date.toISOString())} · {fmtClock(date.toISOString())}
      </p>
      <p className="mt-1 font-mono text-sm font-semibold text-fg">{fmtUsd(point.equity)}</p>
      <p className="font-mono text-[10px] text-muted">cash {fmtUsd(point.cash)}</p>
    </div>
  );
}

export function EquityChart({
  points,
  startingBalance = 100,
  height = 260,
}: {
  points: EquityPoint[];
  startingBalance?: number;
  height?: number;
}) {
  const gradientId = useId().replace(/:/g, "");
  const data = useMemo(
    () =>
      points
        .map((point) => ({ t: new Date(point.t).getTime(), equity: Number(point.equity), cash: Number(point.cash) }))
        .filter((point) => Number.isFinite(point.t) && Number.isFinite(point.equity)),
    [points],
  );

  if (data.length < 2) {
    return (
      <div className="flex items-center justify-center rounded-xl border border-dashed border-white/10 text-xs text-muted" style={{ height }}>
        Collecting equity history…
      </div>
    );
  }

  const first = data[0].equity;
  const last = data[data.length - 1].equity;
  const positive = last >= first;
  const color = positive ? "hsl(157, 90%, 60%)" : "hsl(355, 85%, 62%)";
  const spanMs = data[data.length - 1].t - data[0].t;
  const showDate = spanMs > 1000 * 60 * 60 * 6;

  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 6, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={`equity-${gradientId}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.28} />
              <stop offset="65%" stopColor={color} stopOpacity={0.05} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="rgba(255,255,255,0.045)" strokeDasharray="3 6" vertical={false} />
          <XAxis
            dataKey="t"
            type="number"
            scale="time"
            domain={["dataMin", "dataMax"]}
            tickFormatter={(value: number) =>
              showDate
                ? `${fmtDate(new Date(value).toISOString())}`
                : fmtClock(new Date(value).toISOString())
            }
            tick={{ fill: "rgba(148,163,184,0.67)", fontSize: 10, fontFamily: "JetBrains Mono" }}
            axisLine={false}
            tickLine={false}
            minTickGap={54}
          />
          <YAxis
            domain={[(min: number) => Math.floor(min - 2), (max: number) => Math.ceil(max + 2)]}
            tickFormatter={(value: number) => `$${value.toFixed(0)}`}
            tick={{ fill: "rgba(148,163,184,0.67)", fontSize: 10, fontFamily: "JetBrains Mono" }}
            axisLine={false}
            tickLine={false}
            width={44}
          />
          <ReferenceLine y={startingBalance} stroke="rgba(255,255,255,0.12)" strokeDasharray="4 6" />
          <RechartsTooltip content={<ChartTooltip />} cursor={{ stroke: "rgba(255,255,255,0.2)", strokeDasharray: "3 3" }} />
          <Area
            type="monotone"
            dataKey="equity"
            stroke={color}
            strokeWidth={2}
            fill={`url(#equity-${gradientId})`}
            isAnimationActive={false}
            activeDot={{ r: 3.5, fill: color, stroke: "#05080d", strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
