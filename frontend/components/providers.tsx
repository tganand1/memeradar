"use client";

import { useEffect, type ReactNode } from "react";
import { ToastProvider, useToast } from "@/components/toast";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useLiveStore } from "@/lib/store";
import type { LiveEvent, Snapshot, Trade, TradeFill } from "@/lib/types";

function LiveBridge() {
  const toast = useToast();
  const setSnapshot = useLiveStore((state) => state.setSnapshot);
  const setConnected = useLiveStore((state) => state.setConnected);

  useEffect(() => {
    if (typeof window !== "undefined" && window.localStorage.getItem("memeradar:sound") === "1") {
      useLiveStore.getState().setSoundOn(true);
    }
  }, []);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let disposed = false;
    let attempts = 0;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
    let pingTimer: ReturnType<typeof setInterval> | undefined;

    const apply = (snapshot: Snapshot) => {
      if (snapshot && Array.isArray(snapshot.tokens)) setSnapshot(snapshot);
    };

    const soundEnabled = () => useLiveStore.getState().soundOn;

    const handleEvent = (event: LiveEvent) => {
      if (!event) return;
      if (event.kind === "trade_failed") {
        toast({
          title: `Trade failed · $${event.symbol || "?"}`,
          description: event.reason || "Simulated transaction failure",
          variant: "warning",
        });
        if (soundEnabled()) playSound("error");
        return;
      }
      if (event.kind === "bot_state") {
        const enabled = Boolean(event.data?.enabled);
        toast({
          title: enabled ? "Bot resumed" : "Bot paused",
          description: enabled ? "Scanning and executing again." : "Open positions are being held, no new entries.",
          variant: enabled ? "success" : "warning",
        });
        return;
      }
      if (event.kind === "account_reset") {
        toast({ title: "Account reset", description: "Paper wallet restored to $100.", variant: "info" });
        return;
      }
      if (event.kind === "trade") {
        const trade = (event.data || {}) as Trade;
        const fills = (trade.fills || []) as TradeFill[];
        if (event.action === "buy") {
          toast({
            title: `Bought $${trade.symbol}`,
            description: `$${Number(trade.size_usd).toFixed(2)} filled at ${Number(trade.entry_price).toExponential(2)} · score ${Math.round(trade.score_at_entry)}`,
            variant: "success",
          });
          if (soundEnabled()) playSound("buy");
        } else if (event.action === "close") {
          const pnl = Number(trade.pnl_usd || 0);
          toast({
            title: `Closed $${trade.symbol} · ${pnl >= 0 ? "+" : "−"}$${Math.abs(pnl).toFixed(2)}`,
            description: `${Number(trade.pnl_pct || 0).Fixed(1)}% PnL · ${(trade.exit_reasons || []).join(", ")" || "manual close"}`,
            variant: pnl >= 0 ? "success" : "error",
          });
          if (soundEnabled()) playSound(pnl > 0 ? "win" : "sell");
        } else if (event.action === "partial") {
          const lastFill = fills[fills.length - 1];
          toast({
            title: `Take profit · $${trade.symbol}`,
            description: lastFill
              ? `Sold ${Number(lastFill.tokens).toFixed(0)} tokens at $${Number(lastFill.price).toExponential(2)} · ${lastFill.reason}`
              : "Partial position closed",
            variant: "success",
          });
          if (soundEnabled()) playSound("sell");
        }
      }
    };

    const connect = () => {
      if (disposed) return;
      const url = `${window.location.origin}/ws`;
      try {
        socket = new WebSocket(url);
      } catch {
        scheduleReconnect();
        return;
      }

      socket.onopen = () => {
        attempts = 0;
        setConnected(true);
        pingTimer = setInterval(() => {
          try {
            socket?.send(JSON.stringify({ type: "ping" }));
          } catch {
            /* ignore */
          }
        }, 20000);
      };

      socket.onmessage = (message) => {
        try {
          const parsed = JSON.parse(message.data);
          if (parsed.type === "snapshot" && parsed.payload) {
            apply(parsed.payload as Snapshot);
          } else if (parsed.type === "hello") {
            const snapshot = parsed.payload?.snapshot;
            if (snapshot) apply(snapshot as Snapshot);
          } else if (parsed.type === "event" && parsed.payload) {
            handleEvent(parsed.payload as LiveEvent);
          }
        } catch {
          /* ignore malformed frames */
        }
      };

      socket.onerror = () => {
        try {
          socket?.close();
        } catch {
          /* ignore */
        }
      };

      socket.onclose = () => {
        setConnected(false);
        if (pingTimer) clearInterval(pingTimer);
        pingTimer = undefined;
        if (!disposed) scheduleReconnect();
      };
    };

    const scheduleReconnect = () => {
      attempts += 1;
      const delay = Math.min(800 * attempts, 8000);
      reconnectTimer = setTimeout(connect, delay);
    };

    api.state().then(apply).catch(() => undefined);
    connect();

    const pollTimer = setInterval(() => {
      if (!useLiveStore.getState().connected) {
        api.state().then(apply).catch(() => undefined);
      }
    }, 5000);

    return () => {
      disposed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (pingTimer) clearInterval(pingTimer);
      clearInterval(pollTimer);
      socket?.close();
    };
  }, [setConnected, setSnapshot, toast]);

  return null;
}

export function Providers({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <TooltipProvider delayDuration={180}>
        <LiveBridge />
        {children}
      </TooltipProvider>
    </ToastProvider>
  );
}