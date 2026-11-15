"use client";

import { Activity, ArrowRight, Play, Radar, Sparkles } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { ActivityPanel } from "@/components/dashboard/activity-panel";
import { BreakerBanner } from "@/components/dashboard/breaker-banner";
import { EquityPanel } from "@/components/dashboard/equity-panel";
import { PositionsPanel } from "@/components/dashboard/positions-panel";
import { StatCards } from "@/components/dashboard/stat-cards";
import { TokenFeed } from "@/components/dashboard/token-feed";
import { TradesPanel } from "@/components/dashboard/trades-panel";
import { WhyNoTradesPanel } from "@/components/dashboard/why-no-trades-panel";
import { Shell } from "@/components/shell/shell";
import { useToast } from "@/components/toast";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { fmtUsd, timeAgo } from "@/lib/format";
import { useLiveStore } from "@/lib/store";

export default function DashboardPage() {
  const snapshot = useLiveStore((state) => state.snapshot);
  const toast = useToast();
  const [spawning, setSpawning] = useState(false);

  const spawn = async () => {
    setSpawning(true);
    try {
      await api.spawnDemo(8);
      toast({
        title: "Scanning 8 new launches",
        description: "Fresh demo tokens are entering the radar feed.",
        variant: "info",
      });
    } catch (error) {
      toast({
        title: "Could not spawn tokens",
        description: error instanceof Error ? error.message : "Request failed",
        variant: "error",
      });
    } finally {
      setSpawning(false);
    }
  };

  const resumeBot = async () => {
    try {
      await api.setBot(true);
    } catch (error) {
      toast({
        title: "Could not resume bot",
        description: error instanceof Error ? error.message : "Request failed",
        variant: "error",
      });
    }
  };

  return (
    <Shell>
      <div className="space-y-5">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.24em] text-accent">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-70" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-accent" />
              </span>
              Live Solana scan · {timeAgo(snapshot?.health?.last_token_at)}
            </div>
            <h1 className="mt-2 text-2xl font-bold tracking-tight text-fg sm:text-[32px]">
              Meme coin <span className="text-accent text-glow">radar</span>
            </h1>
            <p className="mt-1 max-w-xl text-sm text-muted">
              Every new launch is scored for safety and momentum, then traded with a simulated{" "}
              <span className="text-fg">{fmtUsd(snapshot?.wallet?.starting_balance ?? 100)}</span> bankroll. Paper only.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Link href="/analytics">
              <Button variant="outline" size="sm" className="gap-1.5">
                <Activity className="h-3.5 w-3.5" /> Analytics
              </Button>
            </Link>
            <Button variant="primary" size="sm" onClick={spawn} disabled={spawning}>
              {spawning ? <Radar className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
              Spawn 8 tokens
            </Button>
          </div>
        </div>

        <BreakerBanner />

        {snapshot && !snapshot.bot_enabled ? (
          <div className="flex flex-wrap items-center gap-3 rounded-xl border border-warn/20 bg-warn/[0.06] px-3.5 py-2.5">
            <span className="flex h-5 w-5 items-center justify-center rounded-full border border-warn/30 text-warn">
              <Play className="h-2.5 w-2.5" />
            </span>
            <p className="flex-1 text-[11px] text-muted">
              <span className="font-semibold text-warn">Bot paused.</span> No new entries or automated exits are being
              taken. Open positions can still be closed manually.
            </p>
            <button
              type="button"
              onClick={resumeBot}
              className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-wider text-warn transition-opacity hover:opacity-80"
            >
              Resume <ArrowRight className="h-3 w-3" />
            </button>
          </div>
        ) : null}

        <StatCards />

        <WhyNoTradesPanel />

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
          <div className="space-y-4 xl:col-span-8">
            <EquityPanel />
            <TokenFeed />
          </div>
          <div className="space-y-4 xl:col-span-4">
            <PositionsPanel />
            <ActivityPanel />
          </div>
        </div>

        <TradesPanel />
      </div>
    </Shell>
  );
}
