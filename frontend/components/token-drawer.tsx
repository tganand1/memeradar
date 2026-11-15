"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import {
  Check as CheckIcon,
  Copy,
  Droplets,
  ExternalLink,
  Globe,
  Loader2,
  MessageCircle,
  RefreshCw,
  Send,
  ShieldAlert,
  ShieldCheck,
  TrendingUp,
  Twitter,
  Users,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";

import { PriceChart } from "@/components/charts/price-chart";
import { ScoreGauge } from "@/components/charts/score-gauge";
import { TokenAvatar } from "@/components/token-avatar";
import { useToast } from "@/components/toast";
import { Badge, verdictTone } from "@/components/ui/badge";
import { api } from "@/lib/api";
import {
  compactUsd,
  duration,
  fmtDate,
  fmtPct,
  fmtPrice,
  fmtUsd,
  pnlTone,
  scoreTone,
  shortAddr,
  timeAgo,
} from "@/lib/format";
import { useLiveStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import type { Check, TokenDetail } from "@/lib/types";

function Section({
  title,
  action,
  children,
}: {
  title: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="border-t border-white/[0.06] px-5 py-5">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-muted">{title}</h3>
        {action}
      </div>
      {children}
    </section>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2.5">
      <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-muted/70">{label}</p>
      <p className="mt-1 truncate font-mono text-[13px] font-semibold text-fg">{value}</p>
      {hint ? <p className="mt-0.5 truncate text-[10px] text-muted">{hint}</p> : null}
    </div>
  );
}

function CheckRow({ check }: { check: Check }) {
  const weight = Number(check.data?.weight ?? check.score ?? 0);
  return (
    <div className="flex items-start gap-2.5 rounded-lg px-1 py-1.5">
      <span
        className={cn(
          "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border",
          check.passed ? "border-accent/30 bg-accent/10 text-accent" : "border-danger/30 bg-danger/10 text-danger",
        )}
      >
        {check.passed ? <CheckIcon className="h-2.5 w-2.5" /> : <X className="h-2.5 w-2.5" />}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <p className="truncate text-[11.5px] font-medium text-fg">{check.name}</p>
          {check.critical ? (
            <span className="rounded border border-danger/25 px-1 py-px font-mono text-[8px] uppercase text-danger">
              critical
            </span>
          ) : null}
          <span className="ml-auto font-mono text-[10px] text-muted">{Number(check.value ?? weight)}</span>
        </div>
        <p className="truncate text-[10px] text-muted">{check.detail || String(check.value ?? "")}</p>
      </div>
    </div>
  );
}

export function TokenDrawer() {
  const mint = useLiveStore((state) => state.selectedMint);
  const closeToken = useLiveStore((state) => state.closeToken);
  const toast = useToast();
  const [detail, setDetail] = useState<TokenDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!mint) {
      setDetail(null);
      setError(null);
      return;
    }
    let alive = true;
    setLoading(true);
    setError(null);
    api
      .token(mint)
      .then((response) => {
        if (alive) setDetail(response);
      })
      .catch((err) => {
        if (alive) setError(err instanceof Error ? err.message : "Could not load token");
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [mint, reloadKey]);

  const copyMint = async () => {
    if (!mint) return;
    try {
      await navigator.clipboard.writeText(mint);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
      toast({ title: "Mint copied", description: shortAddr(mint, 8), variant: "success", duration: 1800 });
    } catch {
      toast({ title: "Copy failed", variant: "error" });
    }
  };

  const external = (url: string | null | undefined) => {
    if (!url) return undefined;
    return url.startsWith("http") ? url : `https://${url}`;
  };

  const checks: Check[] = detail ? Object.values(detail.checks || {}) : [];
  const checksPassed = checks.filter((check) => check.passed).length;
  const breakdown = detail?.score_breakdown;
  const safetyWeight = Number(breakdown?.safety_weight ?? 60);
  const opportunityWeight = Number(breakdown?.opportunity_weight ?? 40);
  const safetyWeightPct = safetyWeight <= 1 ? safetyWeight * 100 : safetyWeight;
  const opportunityWeightPct = opportunityWeight <= 1 ? opportunityWeight * 100 : opportunityWeight;
  const safetyContributions = Object.entries(breakdown?.safety_contributions || {})
    .map(([id, value]) => ({ id, value: Number(value) }))
    .filter((entry) => Number.isFinite(entry.value) && entry.value !== 0)
    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
    .slice(0, 6);
  const opportunityMetrics = detail ? Object.values(detail.opportunity_metrics || {}) : [];
  const buyThreshold = Number(breakdown?.thresholds?.buy ?? 74);
  const watchThreshold = Number(breakdown?.thresholds?.watch ?? 56);

  return (
    <DialogPrimitive.Root open={Boolean(mint)} onOpenChange={(open) => (!open ? closeToken() : undefined)}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="dialog-overlay fixed inset-0 z-[130] bg-black/65 backdrop-blur-sm" />
        <DialogPrimitive.Content
          className="dialog-content fixed inset-y-0 right-0 z-[131] flex w-full max-w-[580px] flex-col overflow-hidden border-l border-white/[0.08] bg-[#070b11]/97 shadow-2xl backdrop-blur-2xl"
          aria-describedby={undefined}
        >
          <DialogPrimitive.Title className="sr-only">
            {detail ? `${detail.name} analysis` : "Token analysis"}
          </DialogPrimitive.Title>

          <div className="flex items-center justify-between border-b border-white/[0.06] px-5 py-3">
            <span className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
              <ShieldCheck className="h-3.5 w-3.5 text-accent" /> Token intelligence
            </span>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => setReloadKey((key) => key + 1)}
                className="rounded-lg p-1.5 text-muted transition-colors hover:bg-white/5 hover:text-fg"
                aria-label="Refresh"
              >
                <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
              </button>
              <DialogPrimitive.Close className="rounded-lg p-1.5 text-muted transition-colors hover:bg-white/5 hover:text-fg">
                <X className="h-4 w-4" />
                <span className="sr-only">Close</span>
              </DialogPrimitive.Close>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto">
            {loading && !detail ? (
              <div className="space-y-4 p-5">
                <div className="h-14 animate-shimmer rounded-xl bg-white/[0.04]" />
                <div className="h-40 animate-shimmer rounded-xl bg-white/[0.04]" />
                <div className="h-64 animate-shimmer rounded-xl bg-white/[0.04]" />
              </div>
            ) : error ? (
              <div className="flex flex-col items-center gap-3 px-6 py-20 text-center">
                <ShieldAlert className="h-7 w-7 text-danger" />
                <p className="text-sm font-medium text-fg">Could not load this token</p>
                <p className="text-xs text-muted">{error}</p>
                <button
                  type="button"
                  onClick={() => setReloadKey((key) => key + 1)}
                  className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-muted transition-colors hover:text-fg"
                >
                  Retry
                </button>
              </div>
            ) : detail ? (
              <>
                <div className="px-5 pb-4 pt-5">
                  <div className="flex items-start gap-3">
                    <TokenAvatar symbol={detail.symbol} imageUrl={detail.image_url} size={52} />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="truncate text-lg font-bold tracking-tight text-fg">${detail.symbol}</h2>
                        <Badge tone={verdictTone(detail.verdict)}>{detail.verdict}</Badge>
                        {detail.rugged ? <Badge tone="danger">rugged</Badge> : null}
                        {detail.hard_rejected ? <Badge tone="danger">hard reject</Badge> : null}
                        {detail.is_demo ? <Badge tone="neutral">demo</Badge> : null}
                      </div>
                      <p className="mt-0.5 truncate text-xs text-muted">{detail.name}</p>
                      <button
                        type="button"
                        onClick={copyMint}
                        className="mt-1 inline-flex items-center gap-1 rounded font-mono text-[10px] text-muted/80 transition-colors hover:text-fg"
                      >
                        {shortAddr(detail.mint, 10)}
                        {copied ? <CheckIcon className="h-3 w-3 text-accent" /> : <Copy className="h-3 w-3" />}
                      </button>
                    </div>
                    <ScoreGauge score={detail.final_score} size={92} thickness={7} label="Final" />
                  </div>

                  <div className="mt-4 grid grid-cols-3 gap-2">
                    <Stat label="Safety" value={`${Math.round(detail.safety_score)}/100`} hint={`${checksPassed}/${checks.length} checks`} />
                    <Stat label="Momentum" value={`${Math.round(detail.opportunity_score)}/100`} hint="opportunity" />
                    <Stat label="Peak" value={fmtPct(detail.peak_gain_pct, 0)} hint="since launch" />
                  </div>

                  {detail.decision_reason ? (
                    <div className="mt-3 rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2.5">
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono text-[9px] uppercase tracking-wider text-muted">Bot decision</span>
                        <Badge tone={detail.decision === "BUY" ? "buy" : "neutral"}>{detail.decision || "SKIP"}</Badge>
                      </div>
                      <p className="mt-1 text-[11px] leading-relaxed text-fg/85">{detail.decision_reason}</p>
                    </div>
                  ) : null}

                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {[
                      {
                        label: "DexScreener",
                        href: detail.links?.dexscreener || `https://dexscreener.com/solana/${detail.mint}`,
                      },
                      {
                        label: "Solscan",
                        href: detail.links?.solscan || `https://solscan.io/token/${detail.mint}`,
                      },
                      {
                        label: "RugCheck",
                        href: detail.links?.rugcheck || `https://rugcheck.xyz/tokens/${detail.mint}`,
                      },
                      {
                        label: "pump.fun",
                        href: detail.links?.pumpfun || `https://pump.fun/coin/${detail.mint}`,
                      },
                    ]
                      .filter((link) => Boolean(link.href))
                      .map((link) => (
                        <a
                          key={link.label}
                          href={link.href}
                          target="_blank"
                          rel="noreferrer noopener"
                          className="inline-flex items-center gap-1 rounded-md border border-white/[0.07] bg-white/[0.02] px-2 py-1 text-[10px] text-muted transition-colors hover:border-white/15 hover:text-fg"
                        >
                          {link.label} <ExternalLink className="h-2.5 w-2.5" />
                        </a>
                      ))}
                    {detail.website ? (
                      <a
                        href={external(detail.website)}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="inline-flex items-center gap-1 rounded-md border border-white/[0.07] px-2 py-1 text-[10px] text-muted hover:text-fg"
                      >
                        <Globe className="h-2.5 w-2.5" /> site
                      </a>
                    ) : null}
                    {detail.twitter ? (
                      <a
                        href={external(detail.twitter)}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="inline-flex items-center gap-1 rounded-md border border-white/[0.07] px-2 py-1 text-[10px] text-muted hover:text-fg"
                      >
                        <Twitter className="h-2.5 w-2.5" /> x
                      </a>
                    ) : null}
                    {detail.telegram ? (
                      <a
                        href={external(detail.telegram)}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="inline-flex items-center gap-1 rounded-md border border-white/[0.07] px-2 py-1 text-[10px] text-muted hover:text-fg"
                      >
                        <Send className="h-2.5 w-2.5" /> tg
                      </a>
                    ) : null}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2 px-5 pb-4 sm:grid-cols-4">
                  <Stat label="Price" value={fmtPrice(detail.price_usd)} hint={timeAgo(detail.last_updated_at)} />
                  <Stat label="Market cap" value={compactUsd(detail.market_cap_usd)} hint={`launch ${compactUsd(detail.initial_market_cap_usd)}`} />
                  <Stat label="Liquidity" value={compactUsd(detail.liquidity_usd)} hint={`init ${compactUsd(detail.initial_liquidity_usd)}`} />
                  <Stat label="Detected" value={fmtDate(detail.detected_at)} hint={timeAgo(detail.detected_at)} />
                </div>

                <Section
                  title="Price action"
                  action={
                    <span className="flex items-center gap-1 font-mono text-[10px] text-muted">
                      <TrendingUp className="h-3 w-3 text-accent" /> live feed
                    </span>
                  }
                >
                  <PriceChart points={detail.price_history || []} height={200} />
                </Section>

                <Section
                  title="Score composition"
                  action={
                    <span className={cn("font-mono text-[10px]", scoreTone(detail.final_score))}>
                      {Math.round(detail.final_score)} / 100
                    </span>
                  }
                >
                  <div className="space-y-2.5">
                    <div>
                      <div className="flex items-center justify-between text-[10px]">
                        <span className="text-muted">Safety · weight {Math.round(safetyWeightPct)}%</span>
                        <span className="font-mono text-fg">{Math.round(detail.safety_score)}</span>
                      </div>
                      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                        <div className="h-full rounded-full bg-accent" style={{ width: `${Math.min(100, detail.safety_score)}%` }} />
                      </div>
                    </div>
                    <div>
                      <div className="flex items-center justify-between text-[10px]">
                        <span className="text-muted">Momentum · weight {Math.round(opportunityWeightPct)}%</span>
                        <span className="font-mono text-fg">{Math.round(detail.opportunity_score)}</span>
                      </div>
                      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                        <div className="h-full rounded-full bg-cyan" style={{ width: `${Math.min(100, detail.opportunity_score)}%` }} />
                      </div>
                    </div>
                    <div className="relative pt-1">
                      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                        <div
                          className={cn(
                            "h-full rounded-full",
                            detail.final_score >= buyThreshold ? "bg-accent" : detail.final_score >= watchThreshold ? "bg-warn" : "bg-danger",
                          )}
                          style={{ width: `${Math.min(100, detail.final_score)}%` }}
                        />
                      </div>
                      <div className="mt-1 flex justify-between font-mono text-[8px] uppercase tracking-wider text-muted/60">
                        <span>avoid</span>
                        <span>watch {watchThreshold}</span>
                        <span>buy {buyThreshold}</span>
                      </div>
                    </div>
                  </div>

                  {safetyContributions.length ? (
                    <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1">
                      {safetyContributions.map((entry) => (
                        <div key={entry.id} className="flex items-center justify-between gap-2 text-[10px]">
                          <span className="truncate text-muted">{entry.id.replace(/_/g, " ")}</span>
                          <span className="font-mono text-fg/80">{entry.value.toFixed(1)}</span>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </Section>

                {detail.hard_rejected || detail.rejected_reasons?.length ? (
                  <div className="mx-5 mt-1 rounded-xl border border-danger/25 bg-danger/[0.07] p-3">
                    <p className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-danger">
                      <ShieldAlert className="h-3 w-3" /> Rejected by safety gate
                    </p>
                    <ul className="mt-1.5 space-y-0.5">
                      {(detail.rejected_reasons?.length ? detail.rejected_reasons : ["Hard rejection triggered"]).map((reason) => (
                        <li key={reason} className="text-[11px] text-muted">
                          · {reason}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                {detail.red_flags?.length || detail.green_flags?.length ? (
                  <Section title="Flags">
                    <div className="flex flex-wrap gap-1.5">
                      {detail.green_flags?.map((flag) => (
                        <span
                          key={flag}
                          className="rounded-md border border-accent/20 bg-accent/[0.06] px-2 py-1 text-[10px] text-accent/90"
                        >
                          {flag}
                        </span>
                      ))}
                      {detail.red_flags?.map((flag) => (
                        <span
                          key={flag}
                          className="rounded-md border border-danger/20 bg-danger/[0.06] px-2 py-1 text-[10px] text-danger/90"
                        >
                          {flag}
                        </span>
                      ))}
                    </div>
                  </Section>
                ) : null}

                <Section
                  title={`Safety checks · ${checksPassed}/${checks.length} passed`}
                  action={<ShieldCheck className="h-3.5 w-3.5 text-accent/70" />}
                >
                  <div className="space-y-0.5">
                    {[...checks]
                      .sort((a, b) => Number(a.passed) - Number(b.passed) || Number(b.critical) - Number(a.critical))
                      .map((check) => (
                        <CheckRow key={check.id} check={check} />
                      ))}
                  </div>
                </Section>

                {opportunityMetrics.length ? (
                  <Section title="Momentum signals" action={<TrendingUp className="h-3.5 w-3.5 text-cyan/70" />}>
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      {opportunityMetrics.map((metric) => (
                        <div key={metric.id} className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-2.5 py-2">
                          <div className="flex items-center justify-between gap-2">
                            <p className="truncate text-[11px] font-medium text-fg">{metric.name}</p>
                            <span className="font-mono text-[10px] text-cyan">{Number(metric.score).toFixed(1)}</span>
                          </div>
                          <p className="mt-0.5 truncate text-[10px] text-muted">{metric.value}</p>
                          <p className="mt-0.5 line-clamp-2 text-[9px] leading-relaxed text-muted/70">{metric.detail}</p>
                        </div>
                      ))}
                    </div>
                  </Section>
                ) : null}

                <Section title="Trade history">
                  {detail.trades?.length ? (
                    <div className="space-y-1.5">
                      {detail.trades.map((trade) => (
                        <div
                          key={trade.id}
                          className="flex items-center gap-2 rounded-lg border border-white/[0.05] bg-white/[0.015] px-2.5 py-2"
                        >
                          <Badge tone={trade.status === "open" ? "watch" : trade.pnl_usd >= 0 ? "buy" : "danger"}>
                            {trade.status}
                          </Badge>
                          <div className="min-w-0 flex-1">
                            <p className="font-mono text-[10px] text-fg">
                              {fmtUsd(trade.size_usd)} @ {fmtPrice(trade.entry_price)}
                            </p>
                            <p className="truncate text-[9px] text-muted">
                              {timeAgo(trade.opened_at)} · {fmtPrice(trade.entry_price)} → {fmtPrice(trade.exit_price)}
                              {trade.exit_reasons?.length ? ` · ${trade.exit_reasons.join(", ")}` : ""}
                            </p>
                          </div>
                          <div className="text-right">
                            <p className={cn("font-mono text-[10px] font-semibold", pnlTone(trade.pnl_usd))}>
                              {trade.status === "closed" ? `${trade.pnl_usd >= 0 ? "+" : "−"}${fmtUsd(Math.abs(trade.pnl_usd))}` : "open"}
                            </p>
                            <p className="font-mono text-[9px] text-muted">
                              {trade.status === "closed" ? fmtPct(trade.pnl_pct) : duration(trade.hold_seconds)}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-[11px] text-muted">No trades were taken on this token.</p>
                  )}
                </Section>

                <Section title="Token metadata">
                  <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-[10px]">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-muted">Creator</span>
                      <span className="truncate font-mono text-fg/80">{shortAddr(detail.creator, 6)}</span>
                    </div>
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-muted">Source</span>
                      <span className="truncate font-mono text-fg/80">{detail.source}</span>
                    </div>
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-muted">Created</span>
                      <span className="truncate font-mono text-fg/80">{fmtDate(detail.created_at)}</span>
                    </div>
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-muted">Initial price</span>
                      <span className="truncate font-mono text-fg/80">{fmtPrice(detail.initial_price_usd)}</span>
                    </div>
                  </div>
                </Section>

                <div className="flex items-center gap-2 border-t border-white/[0.06] px-5 py-4 text-[9px] text-muted/60">
                  <Users className="h-3 w-3" />
                  Safety checks are heuristic. Simulated data. Not financial advice.
                  <Droplets className="ml-auto h-3 w-3" />
                </div>
              </>
            ) : (
              <div className="flex items-center justify-center py-24 text-muted">
                <Loader2 className="h-5 w-5 animate-spin" />
              </div>
            )}
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
