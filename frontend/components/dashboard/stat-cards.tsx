"use client";

import { ArrowDownRight, ArrowUpRight, Crosshair, Radar, Wallet } from "lucide-react";

import { Sparkline } from "@/components/charts/sparkline";
import { Card } from "@/components/ui/card";
import { useLiveStore } from "@/lib/store";
import { fmtPct, fmtUsd, timeAgo } from "@/lib/format";
import { cn } from "@/lib/utils";

function Trend({ value, suffix = "" }: { value: number; suffix?: string }) {
  const positive = value >= 0;
  const Icon = positive ? ArrowUpRight : ArrowDownRight;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 font-mono text-[10px] font-semibold",
        positive ? "border-accent/25 bg-accent/10 text-accent" : "border-danger/25 bg-danger/10 text-danger",
      )}
    >
      <Icon className="h-3 w-3" />
      {fmtPct(value)}
      {suffix}
    </span>
  );
}

export function StatCards() {
  const snapshot = useLiveStore((state) => state.snapshot);
  const wallet = snapshot?.wallet;
  const metrics = snapshot?.metrics;
  const health = snapshot?.health;
  const equityValues = (snapshot?.equity || []).slice(-48).map((point) => point.equity);

  const openPnl = wallet?.unrealized_pnl ?? 0;
  const openValue = wallet?.open_value ?? 0;
  const trades = metrics?.trades ?? 0;
  const wins = metrics?.wins ?? 0;
  const losses = metrics?.losses ?? 0;

  return (
    <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
      <Card className="group relative overflow-hidden p-4">
        <div className="absolute -right-6 -top-8 h-24 w-24 rounded-full bg-accent/[0.06] blur-2xl transition-colors group-hover:bg-accent/[0.1]" />
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.16em] text-muted">
            <Wallet className="h-3 w-3" /> Portfolio
          </span>
          <Trend value={wallet?.today_pnl_pct ?? 0} />
        </div>
        <p className="mt-2 font-mono text-2xl font-bold tracking-tight text-fg sm:text-[28px]">
          {fmtUsd(wallet?.equity ?? 100)}
        </p>
        <div className="mt-1 flex items-end justify-between gap-2">
          <p className="text-[11px] text-muted">
            all time <span className={cn("font-mono", (wallet?.all_time_pnl_pct ?? 0) >= 0 ? "text-accent" : "text-danger")}>
              {fmtPct(wallet?.all_time_pnl_pct ?? 0)}
            </span>
          </p>
          <Sparkline values={equityValues} width={82} height={24} />
        </div>
      </Card>

      <Card className="group relative overflow-hidden p-4">
        <div className="absolute -right-6 -top-8 h-24 w-24 rounded-full bg-cyan/[0.05] blur-2xl" />
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.16em] text-muted">
            <Crosshair className="h-3 w-3" /> Win rate
          </span>
          <span className="font-mono text-[10px] text-muted">{trades} closed</span>
        </div>
        <p className="mt-2 font-mono text-2xl font-bold tracking-tight text-fg sm:text-[28px]">
          {Number(metrics?.win_rate ?? 0).toFixed(1)}%
        </p>
        <div className="mt-2.5 flex items-center gap-2">
          <div className="flex h-1.5 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
            <div className="h-full rounded-full bg-accent" style={{ width: `${Number(metrics?.win_rate ?? 0)}%` }} />
            <div className="h-full rounded-full bg-danger/60" style={{ width: `${100 - Number(metrics?.win_rate ?? 0)}%` }} />
          </div>
          <span className="font-mono text-[10px] text-accent">{wins}W</span>
          <span className="font-mono text-[10px] text-danger">{losses}L</span>
        </div>
      </Card>

      <Card className="group relative overflow-hidden p-4">
        <div className="absolute -right-6 -top-8 h-24 w-24 rounded-full bg-warn/[0.05] blur-2xl" />
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.16em] text-muted">
            <ArrowUpRight className="h-3 w-3" /> Open P&amp;L
          </span>
          <span className="font-mono text-[10px] text-muted">{wallet?.open_count ?? 0} positions</span>
        </div>
        <p
          className={cn(
            "mt-2 font-mono text-2xl font-bold tracking-tight sm:text-[28px]",
            openPnl >= 0 ? "text-accent" : "text-danger",
          )}
        >
          {openPnl >= 0 ? "+" : "−"}
          {fmtUsd(Math.abs(openPnl))}
        </p>
        <p className="mt-1 text-[11px] text-muted">
          exposure <span className="font-mono text-fg">{fmtUsd(openValue)}</span> · cash{" "}
          <span className="font-mono text-fg">{fmtUsd(wallet?.cash ?? 0)}</span>
        </p>
      </Card>

      <Card className="group relative overflow-hidden p-4">
        <div className="absolute -right-4 -top-6 h-20 w-20 rounded-full border border-accent/20">
          <div className="absolute inset-1 animate-radar-sweep rounded-full bg-[conic-gradient(from_0deg,hsl(var(--accent)/0.22),transparent_45%)]" />
        </div>
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.16em] text-muted">
            <Radar className="h-3 w-3" /> Scanner
          </span>
          <span className="flex items-center gap-1 font-mono text-[10px] text-accent">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
            live
          </span>
        </div>
        <p className="mt-2 font-mono text-2xl font-bold tracking-tight text-fg sm:text-[28px]">
          {health?.tokens_per_minute ?? 0}
          <span className="ml-1 text-xs font-medium text-muted">tokens/min</span>
        </p>
        <p className="mt-1 text-[11px] text-muted">
          last scan <span className="font-mono text-fg">{timeAgo(health?.last_token_at)}</span> ·{" "}
          {Object.values(health?.sources || {}).filter((source) => source.status === "ok" || source.status === "live").length} feeds online
        </p>
      </Card>
    </div>
  );
}
