"use client";

import { Clock3, Database, Radar, Search, Volume2, VolumeX, Zap } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { SearchOverlay } from "@/components/search-overlay";
import { useToast } from "@/components/toast";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Tooltip } from "@/components/ui/tooltip";
import { api } from "@/lib/api";
import { fmtUsd } from "@/lib/format";
import { useLiveStore } from "@/lib/store";
import { cn } from "@/lib/utils";

export function Topbar() {
  const snapshot = useLiveStore((state) => state.snapshot);
  const connected = useLiveStore((state) => state.connected);
  const soundOn = useLiveStore((state) => state.soundOn);
  const toggleSound = useLiveStore((state) => state.toggleSound);
  const toast = useToast();
  const [searchOpen, setSearchOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [clock, setClock] = useState<string | null>(null);

  useEffect(() => {
    const tick = () =>
      setClock(
        new Date().toLocaleTimeString("en-GB", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          timeZone: "UTC",
        }),
      );
    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setSearchOpen((current) => !current);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const botEnabled = snapshot?.bot_enabled ?? false;

  const toggleBot = async (next: boolean) => {
    setPending(true);
    try {
      await api.setBot(next);
    } catch (error) {
      toast({
        title: "Could not update bot",
        description: error instanceof Error ? error.message : "Request failed",
        variant: "error",
      });
    } finally {
      setPending(false);
    }
  };

  return (
    <header className="sticky top-0 z-40 border-b border-white/[0.06] bg-[#05080d]/78 backdrop-blur-xl">
      <div className="flex h-14 items-center gap-2 px-4 sm:px-6">
        <Link href="/" className="mr-1 flex items-center gap-2 lg:hidden">
          <Radar className="h-5 w-5 text-accent" />
          <span className="text-sm font-bold tracking-tight">
            Meme<span className="text-accent">Radar</span>
          </span>
        </Link>

        <div className="hidden items-center gap-2 md:flex">
          <span
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 font-mono text-[10px] font-semibold uppercase tracking-wider",
              connected
                ? "border-accent/25 bg-accent/[0.08] text-accent"
                : "border-danger/25 bg-danger/[0.08] text-danger",
            )}
          >
            <span className="relative flex h-1.5 w-1.5">
              {connected ? (
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-60" />
              ) : null}
              <span
                className={cn("relative inline-flex h-1.5 w-1.5 rounded-full", connected ? "bg-accent" : "bg-danger")}
              />
            </span>
            LIVE DATA
          </span>
          <div className="flex items-center gap-1 rounded-md border border-white/[0.07] bg-white/[0.02] px-2 py-1 font-mono text-[9px] text-muted">
            {Object.entries(snapshot?.health?.sources || {
              helius: { status: "online" },
              dexscreener: { status: "online" },
              geckoterminal: { status: "online" },
              rugcheck: { status: "online" },
            }).map(([name, src]) => (
              <Tooltip key={name} label={`${name}: ${src.status}`}>
                <span className="flex items-center gap-1">
                  <span
                    className={cn(
                      "h-1.5 w-1.5 rounded-full",
                      src.status === "online" || src.status === "live" || src.status === "polling"
                        ? "bg-accent"
                        : src.status === "starting" || src.status === "connecting"
                        ? "bg-warn animate-pulse"
                        : "bg-danger",
                    )}
                  />
                  <span className="uppercase">{name.slice(0, 3)}</span>
                </span>
              </Tooltip>
            ))}
          </div>
          <div className="flex items-center gap-1 hidden sm:flex">
            <Badge tone="neutral" className="px-2 py-1">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-60" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-accent" />
              </span>
              <span className="font-mono text-[10px] font-semibold text-fg">LIVE DATA</span>
            </Badge>
            <div className="flex items-center gap-0.5">
              {["helius", "dexscreener", "geckoterminal", "rugcheck"].map((name) => {
                const src = snapshot?.health?.sources?.[name];
                const status = src?.status ?? "offline";
                const online = status === "online" || status === "live" || status === "polling";
                const starting = status === "starting" || status === "connecting";
                return (
                  <Tooltip key={name} label={`${name}: ${src?.detail || status}`}>
                    <span className="flex items-center gap-1">
                      <span
                        className={cn(
                          "h-1.5 w-1.5 rounded-full",
                          online ? "bg-accent" : starting ? "bg-warn animate-pulse" : "bg-danger",
                        )}
                      />
                      <span className="uppercase text-[9px]">{name.slice(0, 3)}</span>
                    </span>
                  </Tooltip>
                );
              })}
            </div>
          </div>
          {snapshot?.breaker?.active ? <Badge tone="danger">Breaker</Badge> : null}
        </div>

        <button
          type="button"
          onClick={() => setSearchOpen(true)}
          className="group ml-auto flex h-9 w-9 shrink-0 items-center justify-center gap-2 rounded-xl border border-white/[0.07] bg-white/[0.025] px-0 text-left text-xs text-muted transition-colors hover:border-white/15 hover:bg-white/[0.05] sm:w-full sm:max-w-[240px] sm:justify-start sm:px-3 md:max-w-[280px]"
        >
          <Search className="h-3.5 w-3.5 shrink-0" />
          <span className="hidden flex-1 truncate sm:block">Search tokens…</span>
          <kbd className="hidden rounded border border-white/10 bg-white/5 px-1 py-0.5 font-mono text-[9px] text-muted/80 sm:inline">
            ⌘K
          </kbd>
        </button>

        <div className="flex items-center gap-1.5 sm:gap-2">
          <div className="hidden items-center gap-1.5 rounded-lg border border-white/[0.06] bg-white/[0.02] px-2 py-1.5 lg:flex">
            <Zap className="h-3 w-3 text-warn" />
            <span className="font-mono text-[11px] text-muted">
              SOL <span className="text-fg">{fmtUsd(snapshot?.sol_price ?? 0)}</span>
            </span>
          </div>

          <div className="hidden items-center gap-1.5 px-2 font-mono text-[11px] text-muted xl:flex">
            <Clock3 className="h-3 w-3" />
            {clock ?? "--:--:--"} UTC
          </div>

          <Tooltip label={soundOn ? "Mute alerts" : "Enable sound alerts"}>
            <button
              type="button"
              onClick={toggleSound}
              className={cn(
                "flex h-9 w-9 items-center justify-center rounded-xl border transition-colors",
                soundOn
                  ? "border-accent/25 bg-accent/[0.08] text-accent"
                  : "border-white/[0.07] bg-white/[0.02] text-muted hover:text-fg",
              )}
              aria-label="Toggle sound"
            >
              {soundOn ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
            </button>
          </Tooltip>

          <div
            className={cn(
              "flex h-9 items-center gap-2 rounded-xl border px-2.5 transition-colors",
              botEnabled ? "border-accent/25 bg-accent/[0.06]" : "border-white/[0.07] bg-white/[0.02]",
            )}
          >
            <span
              className={cn(
                "font-mono text-[10px] font-semibold uppercase tracking-wider",
                botEnabled ? "text-accent" : "text-muted",
              )}
            >
              {botEnabled ? "Bot on" : "Bot off"}
            </span>
            <Switch checked={botEnabled} onCheckedChange={toggleBot} disabled={pending} aria-label="Toggle bot" />
          </div>
        </div>
      </div>

      <SearchOverlay open={searchOpen} onOpenChange={setSearchOpen} />
    </header>
  );
}
