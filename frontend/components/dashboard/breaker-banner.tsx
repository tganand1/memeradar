"use client";

import { ShieldAlert, ShieldCheck } from "lucide-react";

import { useLiveStore } from "@/lib/store";
import { cn } from "@/lib/utils";

export function BreakerBanner() {
  const breaker = useLiveStore((state) => state.snapshot?.breaker);
  if (!breaker) return null;

  if (!breaker.active) {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-accent/15 bg-accent/[0.04] px-3.5 py-2 text-[11px] text-muted">
        <ShieldCheck className="h-3.5 w-3.5 text-accent" />
        <span>
          Risk guard armed · daily circuit breaker at{" "}
          <span className="font-mono text-fg">{breaker.limit_pct.toFixed(0)}%</span> drawdown · current{" "}
          <span className="font-mono text-fg">{Math.max(0, breaker.drawdown_today_pct).toFixed(2)}%</span>
        </span>
      </div>
    );
  }

  return (
    <div className="relative overflow-hidden rounded-xl border border-danger/30 bg-danger/[0.08] px-4 py-3">
      <div className="absolute inset-y-0 left-0 w-1 bg-danger" />
      <div className="flex items-start gap-3">
        <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-danger" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-danger">Circuit breaker tripped — trading halted</p>
          <p className="mt-0.5 text-xs text-muted">
            {breaker.reason || `Daily drawdown exceeded ${breaker.limit_pct.toFixed(0)}%.`} Drawdown{" "}
            <span className="font-mono text-fg">{Math.max(0, breaker.drawdown_today_pct).toFixed(2)}%</span> vs limit{" "}
            <span className="font-mono text-fg">{breaker.limit_pct.toFixed(0)}%</span>. Resumes{" "}
            {breaker.resets_at ? new Date(breaker.resets_at).toLocaleString() : "next UTC day"}.
          </p>
        </div>
        <span className={cn("hidden shrink-0 rounded-md border border-danger/30 px-2 py-1 font-mono text-[9px] uppercase tracking-wider text-danger sm:block")}>
          Safety lock
        </span>
      </div>
    </div>
  );
}
