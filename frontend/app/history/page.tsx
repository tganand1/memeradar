"use client";

import {
  ArrowDownRight,
  ArrowUpRight,
  ChevronLeft,
  ChevronRight,
  Download,
  Filter,
  RefreshCw,
  Search,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Shell } from "@/components/shell/shell";
import { TokenAvatar } from "@/components/token-avatar";
import { useToast } from "@/components/toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Tooltip } from "@/components/ui/tooltip";
import { api } from "@/lib/api";
import { duration, fmtDateTime, fmtPct, fmtPrice, fmtUsd, pnlTone, timeAgo } from "@/lib/format";
import { useLiveStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import type { Trade } from "@/lib/types";

const STATUS_OPTIONS = [
  { id: "all", label: "All" },
  { id: "open", label: "Open" },
  { id: "closed", label: "Closed" },
];

const RESULT_OPTIONS = [
  { id: "all", label: "Any result" },
  { id: "win", label: "Wins" },
  { id: "loss", label: "Losses" },
  { id: "rug", label: "Rugged" },
];

const SCORE_OPTIONS = [
  { id: 0, label: "Any score" },
  { id: 65, label: "65+" },
  { id: 74, label: "74+" },
  { id: 85, label: "85+" },
];

const PAGE_SIZE = 25;

function Summary() {
  const wallet = useLiveStore((state) => state.snapshot?.wallet);
  const metrics = useLiveStore((state) => state.snapshot?.metrics);

  const cells = [
    {
      label: "Net P&L",
      value: `${(metrics?.total_pnl ?? 0) >= 0 ? "+" : "−"}${fmtUsd(Math.abs(metrics?.total_pnl ?? 0))}`,
      hint: `${fmtPct(metrics?.roi_pct ?? 0)} ROI`,
      tone: (metrics?.total_pnl ?? 0) >= 0 ? "text-accent" : "text-danger",
    },
    {
      label: "Win rate",
      value: `${Number(metrics?.win_rate ?? 0).toFixed(1)}%`,
      hint: `${metrics?.wins ?? 0}W / ${metrics?.losses ?? 0}L`,
      tone: "text-fg",
    },
    {
      label: "Profit factor",
      value: Number(metrics?.profit_factor ?? 0).toFixed(2),
      hint: `expectancy ${fmtUsd(metrics?.expectancy ?? 0)}`,
      tone: "text-fg",
    },
    {
      label: "Avg hold",
      value: duration(metrics?.avg_hold_seconds ?? 0),
      hint: `${metrics?.trades ?? 0} closed trades`,
      tone: "text-fg",
    },
    {
      label: "Fees paid",
      value: fmtUsd(metrics?.total_fees ?? wallet?.total_fees ?? 0),
      hint: `rugs ${metrics?.rug_count ?? 0}`,
      tone: "text-warn",
    },
    {
      label: "Equity",
      value: fmtUsd(wallet?.equity ?? 100),
      hint: `${wallet?.open_count ?? 0} open`,
      tone: "text-fg",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
      {cells.map((cell) => (
        <div key={cell.label} className="rounded-xl border border-white/[0.06] bg-panel/60 px-3.5 py-3 backdrop-blur">
          <p className="font-mono text-[9px] uppercase tracking-[0.16em] text-muted/70">{cell.label}</p>
          <p className={cn("mt-1.5 truncate font-mono text-lg font-semibold tracking-tight", cell.tone)}>{cell.value}</p>
          <p className="mt-0.5 truncate text-[10px] text-muted">{cell.hint}</p>
        </div>
      ))}
    </div>
  );
}

export default function HistoryPage() {
  const toast = useToast();
  const openToken = useLiveStore((state) => state.openToken);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState("all");
  const [result, setResult] = useState("all");
  const [minScore, setMinScore] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    setPage(0);
  }, [status, result, minScore]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.trades({
        status,
        result,
        min_score: minScore || undefined,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      });
      setTrades(response.items || []);
      setTotal(response.total || 0);
    } catch (error) {
      toast({
        title: "Could not load trades",
        description: error instanceof Error ? error.message : "Request failed",
        variant: "error",
      });
    } finally {
      setLoading(false);
    }
  }, [minScore, page, result, status, toast]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return trades;
    return trades.filter(
      (trade) =>
        trade.symbol.toLowerCase().includes(q) ||
        trade.name.toLowerCase().includes(q) ||
        trade.mint.toLowerCase().includes(q),
    );
  }, [trades, query]);

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <Shell>
      <div className="space-y-5">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-muted">Journal</p>
            <h1 className="mt-1.5 text-2xl font-bold tracking-tight text-fg sm:text-[28px]">Trade history</h1>
            <p className="mt-1 text-sm text-muted">
              Every entry, exit and simulated failure recorded by the paper engine.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setRefreshKey((key) => key + 1)} disabled={loading}>
              <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} /> Refresh
            </Button>
            <a href={api.exportUrl()} download="memeradar-trades.csv">
              <Button variant="primary" size="sm">
                <Download className="h-3.5 w-3.5" /> Export CSV
              </Button>
            </a>
          </div>
        </div>

        <Summary />

        <Card className="overflow-hidden">
          <div className="flex flex-col gap-3 border-b border-white/[0.05] p-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-wrap items-center gap-2">
              <span className="flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-widest text-muted/70">
                <Filter className="h-3 w-3" /> Status
              </span>
              <div className="flex rounded-lg border border-white/[0.07] bg-white/[0.02] p-0.5">
                {STATUS_OPTIONS.map((option) => (
                  <button
                    key={option.id}
                    type="button"
                    onClick={() => setStatus(option.id)}
                    className={cn(
                      "rounded-md px-2.5 py-1 font-mono text-[10px] transition-colors",
                      status === option.id ? "bg-white/[0.08] text-fg" : "text-muted hover:text-fg",
                    )}
                  >
                    {option.label}
                  </button>
                ))}
              </div>

              <div className="flex rounded-lg border border-white/[0.07] bg-white/[0.02] p-0.5">
                {RESULT_OPTIONS.map((option) => (
                  <button
                    key={option.id}
                    type="button"
                    onClick={() => setResult(option.id)}
                    className={cn(
                      "rounded-md px-2.5 py-1 font-mono text-[10px] transition-colors",
                      result === option.id ? "bg-white/[0.08] text-fg" : "text-muted hover:text-fg",
                    )}
                  >
                    {option.label}
                  </button>
                ))}
              </div>

              <select
                value={minScore}
                onChange={(event) => setMinScore(Number(event.target.value))}
                className="h-7 rounded-lg border border-white/[0.07] bg-[#0a0f16] px-2 font-mono text-[10px] text-muted outline-none focus:border-accent/30"
              >
                {SCORE_OPTIONS.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Filter this page…"
                className="h-8 w-full rounded-lg border border-white/[0.07] bg-white/[0.02] pl-8 pr-3 text-xs text-fg outline-none placeholder:text-muted/60 focus:border-accent/25 lg:w-56"
              />
            </div>
          </div>

          <div className="hidden grid-cols-[minmax(0,1.4fr)_128px_90px_84px_104px_88px_74px_140px] items-center gap-3 border-b border-white/[0.04] px-5 py-2.5 font-mono text-[9px] uppercase tracking-[0.14em] text-muted/70 lg:grid">
            <span>Token</span>
            <span>Opened</span>
            <span>Status</span>
            <span className="text-right">Size</span>
            <span className="text-right">P&amp;L</span>
            <span className="text-right">Held</span>
            <span className="text-right">Score</span>
            <span>Exit reason</span>
          </div>

          {loading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 8 }).map((_, index) => (
                <div key={index} className="h-11 animate-shimmer rounded-lg bg-white/[0.03]" />
              ))}
            </div>
          ) : visible.length === 0 ? (
            <div className="flex flex-col items-center gap-2 px-6 py-16 text-center">
              <Search className="h-6 w-6 text-muted" />
              <p className="text-sm font-medium text-fg">No trades match those filters</p>
              <p className="text-xs text-muted">Try widening the score range or switching status.</p>
            </div>
          ) : (
            <div className="divide-y divide-white/[0.03]">
              {visible.map((trade) => {
                const closed = trade.status === "closed";
                const pnl = trade.pnl_usd || 0;
                return (
                  <button
                    key={trade.id}
                    type="button"
                    onClick={() => openToken(trade.mint)}
                    className="grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-white/[0.03] lg:grid-cols-[minmax(0,1.4fr)_128px_90px_84px_104px_88px_74px_140px] lg:px-5"
                  >
                    <div className="flex min-w-0 items-center gap-2.5">
                      <TokenAvatar symbol={trade.symbol} imageUrl={trade.image_url} size={30} />
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="truncate text-[12px] font-semibold text-fg">${trade.symbol}</span>
                          <span className="font-mono text-[9px] text-muted">#{trade.id}</span>
                        </div>
                        <p className="truncate text-[10px] text-muted lg:hidden">{timeAgo(trade.opened_at)}</p>
                        <p className="hidden truncate text-[10px] text-muted lg:block">{trade.name}</p>
                      </div>
                    </div>

                    <p className="hidden font-mono text-[10px] text-muted lg:block">{fmtDateTime(trade.opened_at)}</p>

                    <div className="hidden lg:block">
                      <Badge tone={closed ? "neutral" : "watch"}>{trade.status}</Badge>
                    </div>

                    <p className="hidden text-right font-mono text-[11px] text-fg lg:block">{fmtUsd(trade.size_usd)}</p>

                    <div className="text-right">
                      <p className={cn("flex items-center justify-end gap-0.5 font-mono text-[11px] font-semibold", pnlTone(pnl))}>
                        {closed ? (
                          <>
                            {pnl >= 0 ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
                            {pnl >= 0 ? "+" : "−"}
                            {fmtUsd(Math.abs(pnl))}
                          </>
                        ) : (
                          <span className="text-warn">open</span>
                        )}
                      </p>
                      <p className={cn("font-mono text-[10px]", pnlTone(trade.pnl_pct))}>
                        {closed ? fmtPct(trade.pnl_pct) : `${fmtPrice(trade.entry_price)} entry`}
                      </p>
                    </div>

                    <p className="hidden text-right font-mono text-[10px] text-muted lg:block">
                      {duration(trade.hold_seconds)}
                    </p>

                    <p className="hidden text-right font-mono text-[11px] text-fg lg:block">
                      {Math.round(trade.score_at_entry)}
                    </p>

                    <div className="hidden lg:block">
                      <Tooltip
                        label={
                          <span className="font-mono text-[10px]">
                            {(trade.exit_reasons || []).join(" · ") || (closed ? "manual" : "still open")}
                          </span>
                        }
                      >
                        <span className="line-clamp-2 text-[10px] text-muted">
                          {(trade.exit_reasons || []).join(", ") || (closed ? "manual close" : "—")}
                        </span>
                      </Tooltip>
                    </div>

                    <div className="flex justify-end lg:hidden">
                      <Badge tone={closed ? (pnl >= 0 ? "buy" : "danger") : "watch"}>
                        {Math.round(trade.score_at_entry)}
                      </Badge>
                    </div>
                  </button>
                );
              })}
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-white/[0.05] px-4 py-3">
            <p className="text-[10px] text-muted">
              <span className="font-mono text-fg">{total}</span> trades · page{" "}
              <span className="font-mono text-fg">{page + 1}</span> of <span className="font-mono text-fg">{pages}</span>
            </p>
            <div className="flex items-center gap-1.5">
              <Button
                variant="outline"
                size="sm"
                disabled={page === 0 || loading}
                onClick={() => setPage((current) => Math.max(0, current - 1))}
              >
                <ChevronLeft className="h-3.5 w-3.5" /> Prev
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={page + 1 >= pages || loading}
                onClick={() => setPage((current) => current + 1)}
              >
                Next <ChevronRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        </Card>
      </div>
    </Shell>
  );
}
