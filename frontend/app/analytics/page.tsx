"use client";

import {
  Activity,
  BarChart3,
  Beaker,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
  Zap,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Sparkline } from "@/components/charts/sparkline";
import { Shell } from "@/components/shell/shell";
import { TokenAvatar } from "@/components/token-avatar";
import { useToast } from "@/components/toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Tooltip } from "@/components/ui/tooltip";
import { api } from "@/lib/api";
import { dayName, fmtPct, fmtUsd, pnlTone } from "@/lib/format";
import { useLiveStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import type { Analytics, BacktestResult } from "@/lib/types";

function Kpi({ label, value, hint, tone }: { label: string; value: string; hint: string; tone?: string }) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-3.5 py-3">
      <p className="font-mono text-[9px] uppercase tracking-[0.16em] text-muted/70">{label}</p>
      <p className={cn("mt-1.5 truncate font-mono text-xl font-semibold tracking-tight text-fg", tone)}>{value}</p>
      <p className="mt-0.5 truncate text-[10px] text-muted">{hint}</p>
    </div>
  );
}

function ScoreBuckets({ data }: { data: Analytics["score_buckets"] }) {
  if (!data?.length) return <p className="py-6 text-center text-xs text-muted">No closed trades yet.</p>;
  return (
    <div className="space-y-3">
      {data.map((bucket) => (
        <div key={bucket.bucket}>
          <div className="flex items-center justify-between gap-2 text-[10px]">
            <span className="font-mono text-muted">{bucket.bucket}</span>
            <span className="flex items-center gap-2">
              <span className="text-muted">{bucket.trades} trades</span>
              <span className={cn("font-mono font-semibold", pnlTone(bucket.pnl))}>
                {fmtPct(bucket.win_rate, 0)} win · {bucket.pnl >= 0 ? "+" : "−"}
                {fmtUsd(Math.abs(bucket.pnl))}
              </span>
            </span>
          </div>
          <div className="mt-1 flex h-2 overflow-hidden rounded-full bg-white/[0.06]">
            <div className="h-full bg-accent" style={{ width: `${Math.min(100, bucket.win_rate)}%` }} />
            <div className="h-full bg-danger/50" style={{ width: `${Math.min(100, 100 - bucket.win_rate)}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function HourBars({ data }: { data: Analytics["by_hour"] }) {
  const hours = Array.from({ length: 24 }, (_, hour) => data.find((row) => row.hour === hour) || { hour, trades: 0, wins: 0, pnl: 0 });
  const maxAbs = Math.max(...hours.map((row) => Math.abs(row.pnl)), 1);
  const total = hours.reduce((sum, row) => sum + row.trades, 0);

  return (
    <div>
      <div className="flex h-28 items-end gap-[3px]">
        {hours.map((row) => {
          const height = row.trades ? Math.max(8, (Math.abs(row.pnl) / maxAbs) * 100) : 2;
          return (
            <Tooltip
              key={row.hour}
              label={
                <span className="font-mono text-[10px]">
                  {String(row.hour).padStart(2, "0")}:00 UTC · {row.trades} trades ·{" "}
                  <span className={pnlTone(row.pnl)}>
                    {row.pnl >= 0 ? "+" : "−"}
                    {fmtUsd(Math.abs(row.pnl))}
                  </span>
                </span>
              }
            >
              <div className="flex h-full flex-1 cursor-default items-end">
                <div
                  className={cn("w-full rounded-t-sm transition-all", row.pnl >= 0 ? "bg-accent/70" : "bg-danger/70", !row.trades && "bg-white/[0.06]")}
                  style={{ height: `${height}%` }}
                />
              </div>
            </Tooltip>
          );
        })}
      </div>
      <div className="mt-1.5 flex justify-between font-mono text-[8px] text-muted/60">
        {[0, 6, 12, 18, 23].map((hour) => (
          <span key={hour}>{String(hour).padStart(2, "0")}</span>
        ))}
      </div>
      <p className="mt-2 text-[10px] text-muted">
        {total} trades bucketed by UTC entry hour · best window{" "}
        <span className="font-mono text-fg">
          {hours.reduce((best, row) => (row.pnl > best.pnl ? row : best), hours[0]).hour}:00
        </span>
      </p>
    </div>
  );
}

function WeekdayBars({ data }: { data: Analytics["by_weekday"] }) {
  const rows = Array.from({ length: 7 }, (_, weekday) => data.find((row) => row.weekday === weekday) || { weekday, trades: 0, wins: 0, pnl: 0 });
  const maxAbs = Math.max(...rows.map((row) => Math.abs(row.pnl)), 1);
  return (
    <div className="space-y-2">
      {rows.map((row) => (
        <div key={row.weekday} className="flex items-center gap-2">
          <span className="w-8 font-mono text-[10px] text-muted">{dayName(row.weekday)}</span>
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/[0.05]">
            <div
              className={cn("h-full rounded-full", row.pnl >= 0 ? "bg-accent/80" : "bg-danger/80")}
              style={{ width: `${Math.max(2, (Math.abs(row.pnl) / maxAbs) * 100)}%` }}
            />
          </div>
          <span className={cn("w-20 text-right font-mono text-[10px]", pnlTone(row.pnl))}>
            {row.pnl >= 0 ? "+" : "−"}
            {fmtUsd(Math.abs(row.pnl))}
          </span>
          <span className="w-12 text-right font-mono text-[9px] text-muted">{row.trades}t</span>
        </div>
      ))}
    </div>
  );
}

function Heatmap({ data }: { data: Analytics["heatmap"] }) {
  const maxAbs = Math.max(...data.map((cell) => Math.abs(cell.pnl)), 1);
  return (
    <div className="overflow-x-auto">
      <div className="min-w-[560px]">
        <div className="mb-1 grid grid-cols-[32px_repeat(24,minmax(0,1fr))] gap-[2px]">
          <span />
          {Array.from({ length: 24 }, (_, hour) => (
            <span key={hour} className="text-center font-mono text-[7px] text-muted/50">
              {hour % 3 === 0 ? hour : ""}
            </span>
          ))}
        </div>
        {Array.from({ length: 7 }, (_, weekday) => (
          <div key={weekday} className="grid grid-cols-[32px_repeat(24,minmax(0,1fr))] gap-[2px]">
            <span className="flex items-center font-mono text-[8px] text-muted/60">{dayName(weekday)}</span>
            {Array.from({ length: 24 }, (_, hour) => {
              const cell = data.find((entry) => entry.weekday === weekday && entry.hour === hour);
              const pnl = cell?.pnl ?? 0;
              const intensity = Math.min(0.85, Math.max(0.06, Math.abs(pnl) / maxAbs));
              return (
                <div
                  key={hour}
                  title={cell ? `${dayName(weekday)} ${hour}:00 · ${cell.trades} trades · ${fmtUsd(pnl)}` : "No trades"}
                  className="h-5 rounded-[3px] border border-white/[0.03]"
                  style={{
                    background: cell
                      ? pnl >= 0
                        ? `hsl(var(--accent) / ${intensity})`
                        : `hsl(var(--danger) / ${intensity})`
                      : "rgba(255,255,255,0.02)",
                  }}
                />
              );
            })}
          </div>
        ))}
        <div className="mt-2 flex items-center justify-end gap-2 font-mono text-[8px] text-muted/60">
          <span>loss</span>
          <span className="h-2 w-3 rounded-sm bg-danger/60" />
          <span className="h-2 w-3 rounded-sm bg-white/[0.04]" />
          <span className="h-2 w-3 rounded-sm bg-accent/60" />
          <span>profit</span>
        </div>
      </div>
    </div>
  );
}

function FiltersTable({ data }: { data: Analytics["filters"] }) {
  const rows = [...(data || [])].sort((a, b) => b.passed_trades + b.failed_trades - (a.passed_trades + a.failed_trades)).slice(0, 9);
  if (!rows.length) return <p className="py-6 text-center text-xs text-muted">No filter statistics yet.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] text-left">
        <thead>
          <tr className="border-b border-white/[0.05] font-mono text-[9px] uppercase tracking-wider text-muted/60">
            <th className="py-1.5 pr-2 font-normal">Check</th>
            <th className="px-2 py-1.5 text-right font-normal">Passed</th>
            <th className="px-2 py-1.5 text-right font-normal">Pass win%</th>
            <th className="px-2 py-1.5 text-right font-normal">Failed</th>
            <th className="px-2 py-1.5 text-right font-normal">Fail win%</th>
            <th className="py-1.5 pl-2 text-right font-normal">Edge</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const edge = (row.passed_win_rate ?? 0) - (row.failed_win_rate ?? 0);
            return (
              <tr key={row.id} className="border-b border-white/[0.03] text-[11px] last:border-0">
                <td className="py-1.5 pr-2 text-fg/85">{row.name}</td>
                <td className="px-2 py-1.5 text-right font-mono text-muted">{row.passed_trades}</td>
                <td className="px-2 py-1.5 text-right font-mono text-accent">
                  {row.passed_win_rate !== null ? `${row.passed_win_rate.toFixed(0)}%` : "—"}
                </td>
                <td className="px-2 py-1.5 text-right font-mono text-muted">{row.failed_trades}</td>
                <td className="px-2 py-1.5 text-right font-mono text-danger">
                  {row.failed_win_rate !== null ? `${row.failed_win_rate.toFixed(0)}%` : "—"}
                </td>
                <td className={cn("py-1.5 pl-2 text-right font-mono font-semibold", edge >= 0 ? "text-accent" : "text-danger")}>
                  {edge >= 0 ? "+" : ""}
                  {edge.toFixed(0)}pp
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function WhatIf({ data }: { data: Analytics["what_if"] }) {
  const best = data?.reduce((top, row) => (row.pnl > top.pnl ? row : top), data[0]);
  if (!data?.length) return <p className="py-6 text-center text-xs text-muted">Run more trades to project thresholds.</p>;
  return (
    <div className="space-y-1.5">
      {data.map((row) => (
        <div
          key={row.threshold}
          className={cn(
            "grid grid-cols-[64px_1fr_64px_80px] items-center gap-2 rounded-lg px-2 py-1.5 text-[10px]",
            row.threshold === best?.threshold ? "border border-accent/20 bg-accent/[0.05]" : "border border-transparent",
          )}
        >
          <span className="font-mono text-muted">score ≥{row.threshold}</span>
          <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.05]">
            <div className="h-full rounded-full bg-cyan/70" style={{ width: `${Math.min(100, row.win_rate)}%` }} />
          </div>
          <span className="text-right font-mono text-muted">{row.trades}t · {row.win_rate.toFixed(0)}%</span>
          <span className={cn("text-right font-mono font-semibold", pnlTone(row.pnl))}>
            {row.pnl >= 0 ? "+" : "−"}
            {fmtUsd(Math.abs(row.pnl))}
          </span>
        </div>
      ))}
      {best ? (
        <p className="pt-1 text-[10px] text-muted">
          Highest simulated P&L at minimum score <span className="font-mono text-fg">{best.threshold}</span>.
        </p>
      ) : null}
    </div>
  );
}

function TokenList({
  items,
  kind,
}: {
  items: Analytics["missed_opportunities"] | Analytics["bullets_dodged"];
  kind: "missed" | "dodged";
}) {
  const openToken = useLiveStore((state) => state.openToken);
  if (!items?.length) {
    return (
      <p className="py-5 text-center text-[11px] text-muted">
        {kind === "missed" ? "No major missed runners." : "No rug pulls dodged yet."}
      </p>
    );
  }
  return (
    <div className="space-y-1">
      {items.slice(0, 6).map((token) => (
        <button
          key={token.mint}
          type="button"
          onClick={() => openToken(token.mint)}
          className="flex w-full items-center gap-2.5 rounded-lg px-1.5 py-1.5 text-left transition-colors hover:bg-white/[0.04]"
        >
          <TokenAvatar symbol={token.symbol} imageUrl={token.image_url} size={26} />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5">
              <span className="truncate text-[11px] font-semibold text-fg">${token.symbol}</span>
              <Badge tone={token.verdict === "BUY" ? "buy" : token.verdict === "WATCH" ? "watch" : "avoid"}>
                {token.verdict}
              </Badge>
              {"rugged" in token && token.rugged ? <Badge tone="danger">rug</Badge> : null}
            </div>
            <p className="truncate text-[9px] text-muted">{token.reasons?.[0] || "—"}</p>
          </div>
          <div className="text-right">
            <p className={cn("font-mono text-[11px] font-semibold", kind === "missed" ? "text-accent" : "text-danger")}>
              {fmtPct(token.peak_gain_pct, 0)}
            </p>
            <p className="font-mono text-[9px] text-muted">score {Math.round(token.final_score)}</p>
          </div>
        </button>
      ))}
    </div>
  );
}

function BacktestPanel() {
  const toast = useToast();
  const [minScore, setMinScore] = useState(74);
  const [startingBalance, setStartingBalance] = useState(100);
  const [stopLoss, setStopLoss] = useState(25);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [running, setRunning] = useState(false);

  const run = async () => {
    setRunning(true);
    try {
      const response = await api.backtest({
        strategy: {
          min_score_buy: Number(minScore),
          exits: { stop_loss_pct: -Math.abs(Number(stopLoss)) / 100 },
        },
        paper: { starting_balance: Number(startingBalance) },
      });
      setResult(response);
      toast({
        title: "Backtest complete",
        description: `${response.metrics.win_rate.toFixed(1)}% win rate · ${fmtPct(response.metrics.roi_pct)} ROI across ${response.trades.length} trades.`,
        variant: "success",
      });
    } catch (error) {
      toast({
        title: "Backtest failed",
        description: error instanceof Error ? error.message : "Request failed",
        variant: "error",
      });
    } finally {
      setRunning(false);
    }
  };

  const values = (result?.equity_curve || []).map((point) => point.equity);

  return (
    <Card>
      <CardHeader className="items-center">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Beaker className="h-3.5 w-3.5 text-cyan" /> Strategy backtest
          </CardTitle>
          <p className="mt-0.5 text-xs text-muted">Replay stored tokens through alternate risk settings</p>
        </div>
        <Button variant="primary" size="sm" onClick={run} disabled={running}>
          {running ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
          Run replay
        </Button>
      </CardHeader>
      <div className="border-t border-white/[0.05] p-4">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
          <label className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-2.5 py-2">
            <span className="font-mono text-[9px] uppercase tracking-wider text-muted">Min score</span>
            <input
              type="number"
              min={0}
              max={100}
              value={minScore}
              onChange={(event) => setMinScore(Number(event.target.value))}
              className="mt-0.5 w-full bg-transparent font-mono text-sm text-fg outline-none"
            />
          </label>
          <label className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-2.5 py-2">
            <span className="font-mono text-[9px] uppercase tracking-wider text-muted">Bankroll $</span>
            <input
              type="number"
              min={10}
              value={startingBalance}
              onChange={(event) => setStartingBalance(Number(event.target.value))}
              className="mt-0.5 w-full bg-transparent font-mono text-sm text-fg outline-none"
            />
          </label>
          <label className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-2.5 py-2">
            <span className="font-mono text-[9px] uppercase tracking-wider text-muted">Stop loss %</span>
            <input
              type="number"
              min={1}
              max={99}
              value={stopLoss}
              onChange={(event) => setStopLoss(Number(event.target.value))}
              className="mt-0.5 w-full bg-transparent font-mono text-sm text-fg outline-none"
            />
          </label>
          {result ? (
            <>
              <Kpi label="Final equity" value={fmtUsd(result.metrics.final_equity)} hint={fmtPct(result.metrics.roi_pct)} />
              <Kpi
                label="Win rate"
                value={`${result.metrics.win_rate.toFixed(1)}%`}
                hint={`${result.trades.length} taken / ${result.scanned} scanned`}
              />
              <Kpi label="Max drawdown" value={fmtPct(-result.metrics.max_drawdown, 1, false)} hint={`PF ${result.metrics.profit_factor.toFixed(2)}`} />
            </>
          ) : (
            <div className="col-span-2 flex items-center gap-2 rounded-lg border border-dashed border-white/[0.08] px-3 text-[10px] text-muted sm:col-span-3 lg:col-span-3">
              <Zap className="h-3.5 w-3.5 text-warn" /> Uses recorded checks, AMM slippage and cost model.
            </div>
          )}
        </div>

        {result ? (
          <div className="mt-4 space-y-3">
            <div className="flex items-center gap-3 rounded-xl border border-white/[0.06] bg-black/20 px-3 py-2">
              <Sparkline values={values} width={160} height={36} />
              <div className="flex flex-1 flex-wrap gap-x-4 gap-y-1 font-mono text-[10px] text-muted">
                <span>scanned <span className="text-fg">{result.scanned}</span></span>
                <span>bought <span className="text-fg">{result.bought}</span></span>
                <span>avoided <span className="text-fg">{result.avoided}</span></span>
                <span>rugs dodged <span className="text-accent">{result.bullets_dodged}</span></span>
                <span>missed <span className="text-danger">{result.missed_opportunities}</span></span>
              </div>
            </div>
            <div className="space-y-1">
              {result.trades.slice(-6).map((trade, index) => (
                <div key={`${trade.mint}-${index}`} className="flex items-center gap-2 rounded-lg border border-white/[0.04] px-2.5 py-1.5 text-[10px]">
                  <span className="font-semibold text-fg">${trade.symbol}</span>
                  <span className="font-mono text-muted">score {Math.round(trade.score)}</span>
                  <span className="ml-auto font-mono text-muted">{fmtUsd(trade.size_usd)}</span>
                  <span className={cn("w-20 text-right font-mono font-semibold", pnlTone(trade.pnl_usd))}>
                    {trade.pnl_usd >= 0 ? "+" : "−"}
                    {fmtUsd(Math.abs(trade.pnl_usd))} ({fmtPct(trade.pnl_pct)})
                  </span>
                  <span className="hidden w-32 truncate text-right text-muted sm:block">
                    {trade.exit_reasons?.join(", ") || "—"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </Card>
  );
}

export default function AnalyticsPage() {
  const toast = useToast();
  const snapshot = useLiveStore((state) => state.snapshot);
  const [data, setData] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(
    async (initial = false) => {
      if (initial) setLoading(true);
      else setRefreshing(true);
      try {
        setData(await api.analytics());
      } catch (error) {
        toast({
          title: "Could not load analytics",
          description: error instanceof Error ? error.message : "Request failed",
          variant: "error",
        });
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [toast],
  );

  useEffect(() => {
    void load(true);
    const timer = setInterval(() => void load(false), 30000);
    return () => clearInterval(timer);
  }, [load]);

  const metrics = data?.metrics || snapshot?.metrics;

  return (
    <Shell>
      <div className="space-y-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-muted">Intelligence</p>
            <h1 className="mt-1.5 text-2xl font-bold tracking-tight text-fg sm:text-[28px]">Strategy analytics</h1>
            <p className="mt-1 text-sm text-muted">Where the edge comes from — and what the safety gate keeps you out of.</p>
          </div>
          <Button variant="outline" size="sm" onClick={() => void load(false)} disabled={refreshing || loading}>
            <RefreshCw className={cn("h-3.5 w-3.5", refreshing && "animate-spin")} /> Refresh
          </Button>
        </div>

        {loading ? (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            {Array.from({ length: 6 }).map((_, index) => (
              <div key={index} className="h-[86px] animate-shimmer rounded-xl bg-white/[0.03]" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            <Kpi
              label="Win rate"
              value={`${Number(metrics?.win_rate ?? 0).toFixed(1)}%`}
              hint={`${metrics?.wins ?? 0}W / ${metrics?.losses ?? 0}L`}
              tone="text-accent"
            />
            <Kpi
              label="Profit factor"
              value={Number(metrics?.profit_factor ?? 0).toFixed(2)}
              hint={`gross ${fmtUsd(metrics?.gross_profit ?? 0)} / ${fmtUsd(metrics?.gross_loss ?? 0)}`}
            />
            <Kpi label="Expectancy" value={fmtUsd(metrics?.expectancy ?? 0)} hint="per trade" />
            <Kpi label="Max drawdown" value={fmtPct(-(metrics?.max_drawdown ?? 0), 1, false)} hint={`Sharpe ${Number(metrics?.sharpe ?? 0).toFixed(2)}`} tone="text-warn" />
            <Kpi label="Missed runners" value={String(data?.counts?.missed ?? 0)} hint="peak ≥ 900% not bought" tone="text-danger" />
            <Kpi label="Rugs dodged" value={String(data?.counts?.dodged ?? 0)} hint={`${data?.counts?.rejected ?? 0} rejected`} tone="text-accent" />
          </div>
        )}

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Target className="h-3.5 w-3.5 text-muted" /> Score calibration
                </CardTitle>
                <p className="mt-0.5 text-xs text-muted">Win rate by entry score bucket</p>
              </div>
            </CardHeader>
            <div className="px-5 pb-5">{data ? <ScoreBuckets data={data.score_buckets} /> : null}</div>
          </Card>

          <Card>
            <CardHeader>
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Activity className="h-3.5 w-3.5 text-muted" /> Edge by hour
                </CardTitle>
                <p className="mt-0.5 text-xs text-muted">UTC entry timing · P&amp;L per hour</p>
              </div>
            </CardHeader>
            <div className="px-5 pb-5">{data ? <HourBars data={data.by_hour} /> : null}</div>
          </Card>

          <Card>
            <CardHeader>
              <div>
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="h-3.5 w-3.5 text-muted" /> Weekday performance
                </CardTitle>
                <p className="mt-0.5 text-xs text-muted">Realized P&amp;L grouped by entry day</p>
              </div>
            </CardHeader>
            <div className="px-5 pb-5">{data ? <WeekdayBars data={data.by_weekday} /> : null}</div>
          </Card>

          <Card>
            <CardHeader>
              <div>
                <CardTitle className="flex items-center gap-2">
                  <TrendingUp className="h-3.5 w-3.5 text-muted" /> What-if threshold
                </CardTitle>
                <p className="mt-0.5 text-xs text-muted">Replay closed trades at higher minimum scores</p>
              </div>
            </CardHeader>
            <div className="px-5 pb-5">{data ? <WhatIf data={data.what_if} /> : null}</div>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <div>
              <CardTitle className="flex items-center gap-2">
                <Zap className="h-3.5 w-3.5 text-muted" /> Trade heatmap
              </CardTitle>
              <p className="mt-0.5 text-xs text-muted">UTC weekday × hour realized P&amp;L</p>
            </div>
          </CardHeader>
          <div className="px-5 pb-5">{data ? <Heatmap data={data.heatmap} /> : null}</div>
        </Card>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <div>
                <CardTitle className="flex items-center gap-2">
                  <ShieldCheck className="h-3.5 w-3.5 text-accent/80" /> Safety filter effectiveness
                </CardTitle>
                <p className="mt-0.5 text-xs text-muted">Win rate when a check passed vs failed</p>
              </div>
            </CardHeader>
            <div className="px-5 pb-5">{data ? <FiltersTable data={data.filters} /> : null}</div>
          </Card>

          <div className="space-y-4">
            <Card>
              <CardHeader>
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <TrendingUp className="h-3.5 w-3.5 text-accent/80" /> Missed opportunities
                  </CardTitle>
                  <p className="mt-0.5 text-xs text-muted">Tokens the bot skipped that ran hard</p>
                </div>
                <span className="font-mono text-[10px] text-muted">{data?.counts?.missed ?? 0} total</span>
              </CardHeader>
              <div className="px-4 pb-4">
                {data ? <TokenList items={data.missed_opportunities} kind="missed" /> : null}
              </div>
            </Card>
            <Card>
              <CardHeader>
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <ShieldCheck className="h-3.5 w-3.5 text-accent/80" /> Bullets dodged
                  </CardTitle>
                  <p className="mt-0.5 text-xs text-muted">Rugged launches the safety gate rejected</p>
                </div>
                <span className="font-mono text-[10px] text-muted">{data?.counts?.dodged ?? 0} total</span>
              </CardHeader>
              <div className="px-4 pb-4">
                {data ? <TokenList items={data.bullets_dodged} kind="dodged" /> : null}
              </div>
            </Card>
          </div>
        </div>

        <BacktestPanel />
      </div>
    </Shell>
  );
}
