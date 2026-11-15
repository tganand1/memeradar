"use client";

import { ArrowUpRight, Copy, ExternalLink, History } from "lucide-react";
import Link from "next/link";

import { TokenAvatar } from "@/components/token-avatar";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Tooltip } from "@/components/ui/tooltip";
import { duration, fmtPct, fmtPrice, fmtUsd, pnlTone, shortAddr, timeAgo } from "@/lib/format";
import { useLiveStore } from "@/lib/store";
import { cn } from "@/lib/utils";

export function TradesPanel() {
  const trades = useLiveStore((state) => state.snapshot?.trades || []);
  const openToken = useLiveStore((state) => state.openToken);

  return (
    <Card className="overflow-hidden">
      <CardHeader className="items-center border-b border-white/[0.05] pb-3">
        <div>
          <CardTitle className="flex items-center gap-2">
            <History className="h-3.5 w-3.5 text-muted" /> Recent closed trades
          </CardTitle>
          <p className="mt-0.5 text-xs text-muted">Latest exits from the paper engine</p>
        </div>
        <Link
          href="/history"
          className="inline-flex items-center gap-1 rounded-lg border border-white/[0.07] px-2.5 py-1.5 text-[11px] text-muted transition-colors hover:bg-white/[0.05] hover:text-fg"
        >
          All trades <ArrowUpRight className="h-3 w-3" />
        </Link>
      </CardHeader>

      <div className="hidden grid-cols-[minmax(0,1.5fr)_120px_80px_110px_90px_110px] items-center gap-3 border-b border-white/[0.04] px-5 py-2 font-mono text-[9px] uppercase tracking-[0.14em] text-muted/70 lg:grid">
        <span>Token</span>
        <span>Entry → Exit</span>
        <span className="text-right">Size</span>
        <span className="text-right">P&amp;L</span>
        <span className="text-right">Held</span>
        <span className="text-right">Exit</span>
        <span className="text-right">Links</span>
      </div>

      <div className="divide-y divide-white/[0.03]">
        {trades.length === 0 ? (
          <p className="px-5 py-10 text-center text-xs text-muted">No closed trades yet — the bot is still hunting.</p>
        ) : (
          trades.slice(0, 8).map((trade) => {
            const pnl = trade.pnl_usd ?? 0;
            return (
              <button
                key={trade.id}
                type="button"
                onClick={() => openToken(trade.mint)}
                className="grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-white/[0.03] sm:px-5 lg:grid-cols-[minmax(0,1.5fr)_120px_80px_110px_90px_110px]"
              >
                <div className="flex min-w-0 items-center gap-2.5">
                  <TokenAvatar symbol={trade.symbol} imageUrl={trade.image_url} size={30} />
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="truncate text-[12px] font-semibold text-fg">${trade.symbol}</span>
                      <span className="font-mono text-[9px] text-muted">#{trade.id}</span>
                    </div>
                    <p className="truncate text-[10px] text-muted">
                      score {Math.round(trade.score_at_entry)} · {timeAgo(trade.closed_at)}
                    </p>
                  </div>
                </div>

                <div className="hidden font-mono text-[10px] text-muted lg:block">
                  {fmtPrice(trade.entry_price)} <span className="text-muted/40">→</span> {fmtPrice(trade.exit_price)} <span className="text-muted/20">· size</span>
                </div>

                <div className="hidden text-right font-mono text-[11px] text-fg lg:block">{fmtUsd(trade.size_usd)}</div>

                <div className="text-right">
                  <p className={cn("font-mono text-[11px] font-semibold", pnlTone(pnl))}>
                    {pnl >= 0 ? "+" : "−"}
                    {fmtUsd(Math.abs(pnl))}
                  </p>
                  <p className={cn("font-mono text-[10px]", pnlTone(trade.pnl_pct))}>{fmtPct(trade.pnl_pct)}</p>
                </div>

                <div className="hidden text-right font-mono text-[10px] text-muted lg:block">
                  {duration(trade.hold_seconds)}
                </div>

                <div className="hidden justify-end lg:flex">
                  <Tooltip label={<span className="font-mono text-[10px]">{(trade.exit_reasons || []).join(" · ") || "manual"}</span>}>
                    <Badge tone={pnl >= 0 ? "buy" : "danger"}>
                      {(trade.exit_reasons?.[0] || "close").replace(/_/g, " ").slice(0, 14)}
                    </Badge>
                  </Tooltip>
                </div>

                <div className="flex items-center justify-end gap-1 lg:hidden">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      void navigator.clipboard.writeText(trade.mint);
                    }}
                    className="rounded-md border border-white/10 bg-white/5 px-1.5 py-0.5 font-mono text-[9px] text-muted hover:text-fg"
                    title="Copy mint"
                  >
                    <Copy className="h-2.5 w-2.5" />
                  </button>
                </div>

                <div className="hidden lg:flex items-center justify-end gap-1">
                  <a
                    href={`https://dexscreener.com/solana/${trade.mint}`}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="rounded border border-white/[0.07] bg-white/[0.02] px-1.5 py-0.5 font-mono text-[9px] text-muted hover:text-fg"
                    title="DexScreener"
                  >
                    Dex <ExternalLink className="h-2.5 w-2.5" />
                  </a>
                  <a
                    href={`https://solscan.io/token/${trade.mint}`}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="rounded border border-white/[0.07] bg-white/[0.02] px-1.5 py-0.5 font-mono text-[9px] text-muted hover:text-fg"
                    title="Solscan"
                  >
                    Scan <ExternalLink className="h-2.5 w-2.5" />
                  </a>
                  <a
                    href={`https://rugcheck.xyz/tokens/${trade.mint}`}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="rounded border border-white/[0.07] bg-white/[0.02] px-1.5 py-0.5 font-mono text-[9px] text-muted hover:text-fg"
                    title="RugCheck"
                  >
                    Check <ExternalLink className="h-2.5 w-2.5" />
                  </a>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      void navigator.clipboard.writeText(trade.mint);
                    }}
                    className="rounded border border-white/[0.07] bg-white/[0.02] px-1.5 py-0.5 font-mono text-[9px] text-muted hover:text-fg"
                    title="Copy mint"
                  >
                    <Copy className="h-2.5 w-2.5" />
                  </button>
                </div>
              </button>
            );
          })
        )}
      </div>
    </Card>
  );
}
