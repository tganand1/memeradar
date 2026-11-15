"use client";

import { useEffect, useMemo, useState } from "react";

import { EquityChart } from "@/components/charts/equity-chart";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { fmtPct, fmtUsd } from "@/lib/format";
import { useLiveStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import type { EquityPoint } from "@/lib/types";

const RANGES = ["1H", "24H", "7D", "ALL"] as const;
type Range = (typeof RANGES)[number];

export function EquityPanel() {
  const snapshot = useLiveStore((state) => state.snapshot);
  const [range, setRange] = useState<Range>("24H");
  const [fetched, setFetched] = useState<EquityPoint[] | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (range === "24H") {
      setFetched(null);
      return;
    }
    let alive = true;
    setLoading(true);
    api
      .equity(range)
      .then((response) => {
        if (alive) setFetched(response.points || []);
      })
      .catch(() => {
        if (alive) setFetched([]);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [range]);

  const points = useMemo(() => {
    if (range === "24H") return snapshot?.equity || [];
    return fetched ?? snapshot?.equity ?? [];
  }, [range, fetched, snapshot?.equity]);

  const wallet = snapshot?.wallet;
  const start = 100;
  const equity = wallet?.equity ?? start;
  const pnl = equity - start;
  const pnlPct = (pnl / start) * 100;
  const rangeChange = points.length >= 2 ? points[points.length - 1].equity - points[0].equity : 0;

  return (
    <Card className="overflow-hidden">
      <CardHeader className="items-start pb-0">
        <div>
          <CardTitle className="flex items-center gap-2">
            Equity curve
            <span className="rounded border border-white/10 bg-white/[0.04] px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider text-muted">
              paper
            </span>
          </CardTitle>
          <div className="mt-1.5 flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="font-mono text-2xl font-bold tracking-tight text-fg">{fmtUsd(equity)}</span>
            <span className={cn("font-mono text-xs font-medium", pnl >= 0 ? "text-accent" : "text-danger")}>
              {pnl >= 0 ? "+" : "−"}
              {fmtUsd(Math.abs(pnl))} ({fmtPct(pnlPct)})
            </span>
            <span className="text-[11px] text-muted">
              range <span className={cn("font-mono", rangeChange >= 0 ? "text-accent" : "text-danger")}>{rangeChange >= 0 ? "+" : "−"}{fmtUsd(Math.abs(rangeChange))}</span>
            </span>
          </div>
        </div>
        <div className="flex items-center gap-0.5 rounded-lg border border-white/[0.07] bg-white/[0.02] p-0.5">
          {RANGES.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setRange(option)}
              className={cn(
                "rounded-md px-2.5 py-1 font-mono text-[10px] font-medium transition-colors",
                range === option ? "bg-accent/15 text-accent" : "text-muted hover:text-fg",
              )}
            >
              {option}
            </button>
          ))}
        </div>
      </CardHeader>
      <CardContent className="pb-3 pt-3">
        <div className={cn("transition-opacity", loading && "opacity-50")}>
          <EquityChart points={points} startingBalance={start} height={244} />
        </div>
      </CardContent>
    </Card>
  );
}
