"use client";

import { Radar, ShieldAlert } from "lucide-react";
import { useMemo, useState } from "react";

import { TokenAvatar } from "@/components/token-avatar";
import { Badge, verdictTone } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Tooltip } from "@/components/ui/tooltip";
import { compactUsd, fmtPct, fmtPrice, scoreTone, timeAgo } from "@/lib/format";
import { useLiveStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import type { Verdict } from "@/lib/types";

const FILTERS: Array<{ id: "ALL" | Verdict; label: string }> = [
  { id: "ALL", label: "All" },
  { id: "BUY", label: "Buy" },
  { id: "WATCH", label: "Watch" },
  { id: "AVOID", label: "Avoid" },
];

export function TokenFeed() {
  const tokens = useLiveStore((state) => state.snapshot?.tokens || []);
  const openToken = useLiveStore((state) => state.openToken);
  const [filter, setFilter] = useState<"ALL" | Verdict>("ALL");

  const filtered = useMemo(
    () => (filter === "ALL" ? tokens : tokens.filter((token) => token.verdict === filter)),
    [tokens, filter],
  );

  const counts = useMemo(() => {
    const result = { ALL: tokens.length, BUY: 0, WATCH: 0, AVOID: 0 };
    tokens.forEach((token) => {
      if (token.verdict === "BUY") result.BUY += 1;
      else if (token.verdict === "WATCH") result.WATCH += 1;
      else result.AVOID += 1;
    });
    return result;
  }, [tokens]);

  return (
    <Card className="overflow-hidden">
      <CardHeader className="items-center border-b border-white/[0.05] pb-3">
        <div>
          <CardTitle className="flex items-center gap-2">
            <span className="relative flex h-4 w-4 items-center justify-center">
              <span className="absolute h-4 w-4 animate-pulse-ring rounded-full border border-accent/50" />
              <Radar className="h-3.5 w-3.5 text-accent" />
            </span>
            Token radar
          </CardTitle>
          <p className="mt-0.5 text-xs text-muted">New launches scored by safety and momentum</p>
        </div>
        <div className="flex items-center gap-0.5 rounded-lg border border-white/[0.07] bg-white/[0.02] p-0.5">
          {FILTERS.map((option) => (
            <button
              key={option.id}
              type="button"
              onClick={() => setFilter(option.id)}
              className={cn(
                "flex items-center gap-1 rounded-md px-2 py-1 font-mono text-[10px] font-medium transition-colors",
                filter === option.id ? "bg-white/[0.08] text-fg" : "text-muted hover:text-fg",
              )}
            >
              {option.label}
              <span className={cn("text-[9px]", filter === option.id ? "text-accent" : "text-muted/60")}>
                {counts[option.id]}
              </span>
            </button>
          ))}
        </div>
      </CardHeader>

      <div className="hidden grid-cols-[minmax(0,1.7fr)_64px_104px_84px_80px] items-center gap-3 border-b border-white/[0.04] px-5 py-2 font-mono text-[9px] uppercase tracking-[0.16em] text-muted/70 sm:grid">
        <span>Token</span>
        <span className="text-center">Score</span>
        <span className="text-right">Price / MC</span>
        <span className="text-right">Peak</span>
        <span className="text-right">Verdict</span>
      </div>

      <div className="max-h-[560px] overflow-y-auto">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-3 px-6 py-16 text-center">
            <div className="relative flex h-16 w-16 items-center justify-center rounded-full border border-accent/20 radar-grid">
              <div className="absolute inset-0 animate-radar-sweep rounded-full bg-[conic-gradient(from_0deg,hsl(var(--accent)/0.25),transparent_40%)]" />
              <Radar className="relative h-6 w-6 text-accent/70" />
            </div>
            <div>
              <p className="text-sm font-medium text-fg">Warming up the radar</p>
              <p className="mt-1 text-xs text-muted">
                {tokens.length === 0 ? "Waiting for the first token launch…" : "No tokens match this filter."}
              </p>
            </div>
          </div>
        ) : (
          filtered.map((token) => (
            <button
              key={token.mint}
              type="button"
              onClick={() => openToken(token.mint)}
              className="grid w-full grid-cols-[minmax(0,1fr)_56px] items-center gap-3 border-b border-white/[0.03] px-4 py-2.5 text-left transition-colors last:border-0 hover:bg-white/[0.035] sm:grid-cols-[minmax(0,1.7fr)_64px_104px_84px_80px] sm:px-5"
            >
              <div className="flex min-w-0 items-center gap-2.5">
                <TokenAvatar symbol={token.symbol} imageUrl={token.image_url} size={34} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <span className="truncate text-[13px] font-semibold text-fg">${token.symbol}</span>
                    {token.hard_rejected ? (
                      <Tooltip
                        label={
                          <span className="font-mono text-[10px]">{token.rejected_reasons.join(" · ") || "Hard reject"}</span>
                        }
                      >
                        <ShieldAlert className="h-3 w-3 shrink-0 text-danger" />
                      </Tooltip>
                    ) : null}
                  </div>
                  <p className="truncate text-[10px] text-muted">
                    {token.name} · {timeAgo(token.detected_at || token.created_at)}
                  </p>
                </div>
              </div>

              <div className="text-right sm:text-center">
                <span className={cn("font-mono text-sm font-bold", scoreTone(token.final_score))}>
                  {Math.round(token.final_score)}
                </span>
                <div className="mt-1 flex h-1 overflow-hidden rounded-full bg-white/[0.06]">
                  <div
                    className={cn(
                      "h-full",
                      token.final_score >= 74 ? "bg-accent" : token.final_score >= 56 ? "bg-warn" : "bg-danger",
                    )}
                    style={{ width: `${token.final_score}%` }}
                  />
                </div>
              </div>

              <div className="hidden text-right sm:block">
                <p className="font-mono text-[11px] text-fg">{fmtPrice(token.price_usd)}</p>
                <p className="font-mono text-[10px] text-muted">{compactUsd(token.market_cap_usd)}</p>
              </div>

              <div className="hidden text-right sm:block">
                <p
                  className={cn(
                    "font-mono text-[11px] font-medium",
                    token.peak_gain_pct > 0 ? "text-accent" : "text-muted",
                  )}
                >
                  {fmtPct(token.peak_gain_pct, 0)}
                </p>
                <p className="font-mono text-[10px] text-muted">{compactUsd(token.liquidity_usd)} liq</p>
              </div>

              <div className="hidden justify-end sm:flex">
                <Badge tone={verdictTone(token.verdict)}>{token.verdict}</Badge>
              </div>

              <div className="flex justify-end sm:hidden">
                <Badge tone={verdictTone(token.verdict)}>{token.verdict}</Badge>
              </div>
            </button>
          ))
        )}
      </div>

      <div className="flex items-center justify-between border-t border-white/[0.05] px-5 py-2.5 text-[10px] text-muted">
        <span>
          Showing <span className="font-mono text-fg">{filtered.length}</span> of{" "}
          <span className="font-mono text-fg">{tokens.length}</span> cached scans
        </span>
        <span className="font-mono uppercase tracking-wider text-muted/70">click row for full analysis</span>
      </div>
    </Card>
  );
}
