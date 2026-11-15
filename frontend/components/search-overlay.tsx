"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { ArrowRight, Command, Search, X } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { TokenAvatar } from "@/components/token-avatar";
import { useLiveStore } from "@/lib/store";
import { fmtPct, scoreTone } from "@/lib/format";
import { cn } from "@/lib/utils";

const quickLinks = [
  { href: "/", label: "Dashboard" },
  { href: "/history", label: "Trade history" },
  { href: "/analytics", label: "Analytics" },
  { href: "/console", label: "Live console" },
  { href: "/settings", label: "Settings" },
];

export function SearchOverlay({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const snapshot = useLiveStore((state) => state.snapshot);
  const openToken = useLiveStore((state) => state.openToken);
  const [query, setQuery] = useState("");

  const results = useMemo(() => {
    const tokens = snapshot?.tokens || [];
    const q = query.trim().toLowerCase();
    if (!q) return tokens.slice(0, 7);
    return tokens
      .filter(
        (token) =>
          token.symbol.toLowerCase().includes(q) ||
          token.name.toLowerCase().includes(q) ||
          token.mint.toLowerCase().includes(q),
      )
      .slice(0, 8);
  }, [snapshot, query]);

  const select = (mint: string) => {
    openToken(mint);
    onOpenChange(false);
    setQuery("");
  };

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="dialog-overlay fixed inset-0 z-[130] bg-black/70 backdrop-blur-sm" />
        <DialogPrimitive.Content
          className="dialog-center fixed left-1/2 top-[12vh] z-[131] w-[600px] max-w-[calc(100vw-2rem)] -translate-x-1/2 overflow-hidden rounded-2xl border border-white/10 bg-[#080d14]/95 shadow-2xl backdrop-blur-xl"
          aria-describedby={undefined}
        >
          <DialogPrimitive.Title className="sr-only">Search tokens and pages</DialogPrimitive.Title>
          <div className="flex items-center gap-3 border-b border-white/[0.07] px-4">
            <Search className="h-4 w-4 text-muted" />
            <input
              autoFocus
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search tokens, symbols, mints…"
              className="h-12 flex-1 bg-transparent text-sm text-fg outline-none placeholder:text-muted/70"
            />
            <button
              type="button"
              onClick={() => onOpenChange(false)}
              className="rounded-lg p-1.5 text-muted transition-colors hover:bg-white/5 hover:text-fg"
              aria-label="Close search"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="max-h-[52vh] overflow-y-auto p-2">
            {results.length ? (
              <>
                <p className="px-2 py-1.5 font-mono text-[10px] uppercase tracking-widest text-muted/70">Tokens</p>
                {results.map((token) => (
                  <button
                    key={token.mint}
                    type="button"
                    onClick={() => select(token.mint)}
                    className="group flex w-full items-center gap-3 rounded-xl px-2 py-2 text-left transition-colors hover:bg-white/[0.05]"
                  >
                    <TokenAvatar symbol={token.symbol} imageUrl={token.image_url} size={30} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="truncate text-sm font-semibold text-fg">${token.symbol}</span>
                        <span
                          className={cn(
                            "font-mono text-[9px] uppercase",
                            token.verdict === "BUY" ? "text-accent" : token.verdict === "WATCH" ? "text-warn" : "text-danger",
                          )}
                        >
                          {token.verdict}
                        </span>
                      </div>
                      <p className="truncate text-[11px] text-muted">{token.name}</p>
                    </div>
                    <div className="text-right">
                      <p className={cn("font-mono text-xs font-semibold", scoreTone(token.final_score))}>
                        {Math.round(token.final_score)}
                      </p>
                      <p className={cn("font-mono text-[10px]", token.peak_gain_pct > 0 ? "text-accent" : "text-muted")}>
                        {fmtPct(token.peak_gain_pct)}
                      </p>
                    </div>
                    <ArrowRight className="h-3.5 w-3.5 text-muted/40 opacity-0 transition-opacity group-hover:opacity-100" />
                  </button>
                ))}
              </>
            ) : (
              <p className="px-3 py-6 text-center text-sm text-muted">No tokens match “{query}”.</p>
            )}

            <p className="px-2 pb-1.5 pt-3 font-mono text-[10px] uppercase tracking-widest text-muted/70">Navigate</p>
            <div className="grid grid-cols-2 gap-1">
              {quickLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={() => onOpenChange(false)}
                  className="flex items-center justify-between rounded-lg px-2 py-1.5 text-xs text-muted transition-colors hover:bg-white/[0.05] hover:text-fg"
                >
                  {link.label}
                  <ArrowRight className="h-3 w-3 opacity-40" />
                </Link>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-4 border-t border-white/[0.07] px-4 py-2.5 font-mono text-[10px] text-muted/70">
            <span className="flex items-center gap-1">
              <kbd className="rounded border border-white/10 bg-white/5 px-1">↵</kbd> open
            </span>
            <span className="flex items-center gap-1">
              <kbd className="rounded border border-white/10 bg-white/5 px-1">esc</kbd> close
            </span>
            <span className="ml-auto flex items-center gap-1">
              <Command className="h-3 w-3" /> K
            </span>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
