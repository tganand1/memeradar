"use client";

import {
  Activity,
  BarChart3,
  History,
  Radar,
  Settings2,
  TerminalSquare,
  Wallet,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { useLiveStore } from "@/lib/store";
import { fmtPct, fmtUsd, pnlTone } from "@/lib/format";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/", label: "Dashboard", icon: Radar },
  { href: "/history", label: "History", icon: History },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/console", label: "Console", icon: TerminalSquare },
  { href: "/settings", label: "Settings", icon: Settings2 },
];

export function Sidebar() {
  const pathname = usePathname();
  const snapshot = useLiveStore((state) => state.snapshot);
  const wallet = snapshot?.wallet;
  const health = snapshot?.health;

  return (
    <aside className="sticky top-0 hidden h-screen w-[236px] shrink-0 flex-col border-r border-white/[0.06] bg-[#070b11]/70 px-3 py-5 backdrop-blur-xl lg:flex">
      <Link href="/" className="group flex items-center gap-3 px-2">
        <div className="relative flex h-10 w-10 items-center justify-center overflow-hidden rounded-xl border border-accent/25 bg-accent/[0.06]">
          <div className="absolute inset-0 animate-radar-sweep rounded-full bg-[conic-gradient(from_0deg,hsl(var(--accent)/0.3),transparent_38%)]" />
          <Radar className="relative h-5 w-5 text-accent" />
        </div>
        <div>
          <p className="text-[15px] font-bold leading-none tracking-tight text-fg">
            Meme<span className="text-accent">Radar</span>
          </p>
          <p className="mt-1 font-mono text-[9px] uppercase tracking-[0.22em] text-muted">Solana terminal</p>
        </div>
      </Link>

      <div className="mt-7 flex items-center gap-1.5 px-2">
        <span className="relative flex h-1.5 w-1.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-60" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-accent" />
        </span>
        <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted">
          {snapshot?.mode === "live" ? "Live network" : "Simulation"} · 24/7
        </span>
      </div>

      <nav className="mt-4 flex flex-col gap-1">
        {nav.map((item) => {
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium transition-colors",
                active ? "text-fg" : "text-muted hover:bg-white/[0.04] hover:text-fg",
              )}
            >
              {active ? (
                <span className="absolute inset-0 rounded-xl border border-accent/15 bg-accent/[0.07]" />
              ) : null}
              {active ? <span className="absolute left-0 h-5 w-[2px] rounded-full bg-accent" /> : null}
              <Icon className={cn("relative h-4 w-4", active ? "text-accent" : "text-muted group-hover:text-fg")} />
              <span className="relative">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto space-y-3">
        <div className="rounded-xl border border-white/[0.07] bg-white/[0.025] p-3">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-[10px] uppercase tracking-widest text-muted">
              <Wallet className="h-3 w-3" /> Paper wallet
            </span>
            <span className="font-mono text-[9px] text-accent">PAPER</span>
          </div>
          <p className="mt-2 font-mono text-lg font-semibold tracking-tight text-fg">
            {fmtUsd(wallet?.equity ?? 100)}
          </p>
          <div className="mt-1 flex items-center justify-between text-[11px]">
            <span className={cn("font-mono", pnlTone(wallet?.today_pnl ?? 0))}>
              {fmtPct(wallet?.today_pnl_pct ?? 0)} today
            </span>
            <span className="text-muted">{wallet?.open_count ?? 0} open</span>
          </div>
        </div>

        <div className="flex items-center justify-between rounded-xl border border-white/[0.05] px-3 py-2">
          <span className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-muted">
            <Activity className="h-3 w-3" /> Feed
          </span>
          <span className="font-mono text-[10px] text-muted">
            <span className="text-accent">{health?.tokens_per_minute ?? 0}</span>/min
          </span>
        </div>

        <p className="px-2 font-mono text-[9px] leading-relaxed text-muted/60">
          PAPER TRADING ONLY
          <br />
          No wallet · No signatures · No real funds
        </p>
      </div>
    </aside>
  );
}
