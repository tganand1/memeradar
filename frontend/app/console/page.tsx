"use client";

import { Circle, Download, Pause, Play, RefreshCw, Search, Trash2, Terminal } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Shell } from "@/components/shell/shell";
import { useToast } from "@/components/toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { api, API_BASE } from "@/lib/api";
import { fmtTime } from "@/lib/format";
import { useLiveStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import type { LogEntry } from "@/lib/types";

const LEVELS = ["all", "trade", "info", "warning", "error"] as const;
type LevelFilter = (typeof LEVELS)[number];

const levelStyles: Record<string, { text: string; dot: string; row?: string }> = {
  trade: { text: "text-accent", dot: "bg-accent", row: "" },
  info: { text: "text-cyan", dot: "bg-cyan/70", row: "" },
  warning: { text: "text-warn", dot: "bg-warn", row: "bg-warn/[0.025]" },
  error: { text: "text-danger", dot: "bg-danger", row: "bg-danger/[0.04]" },
};

function sortLogs(items: LogEntry[]): LogEntry[] {
  const map = new Map<number, LogEntry>();
  items.forEach((entry) => map.set(entry.id, entry));
  return Array.from(map.values())
    .sort((a, b) => a.id - b.id)
    .slice(-900);
}

export default function ConsolePage() {
  const toast = useToast();
  const connected = useLiveStore((state) => state.connected);
  const snapshotLogs = useLiveStore((state) => state.snapshot?.logs || []);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [level, setLevel] = useState<LevelFilter>("all");
  const [query, setQuery] = useState("");
  const [paused, setPaused] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [floorId, setFloorId] = useState(0);
  const [loading, setLoading] = useState(true);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const lastCountRef = useRef(0);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.logs(600);
      setLogs(sortLogs(response.items || []));
    } catch (error) {
      toast({
        title: "Could not load logs",
        description: error instanceof Error ? error.message : "Request failed",
        variant: "error",
      });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (paused) return;
    setLogs((current) => sortLogs([...current, ...snapshotLogs]));
  }, [snapshotLogs, paused]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return logs.filter((entry) => {
      if (entry.id <= floorId) return false;
      if (level !== "all" && entry.level !== level) return false;
      if (!q) return true;
      return (
        entry.message.toLowerCase().includes(q) ||
        entry.category.toLowerCase().includes(q) ||
        entry.level.toLowerCase().includes(q)
      );
    });
  }, [logs, level, query, floorId]);

  useEffect(() => {
    if (!autoScroll) return;
    if (visible.length === lastCountRef.current) return;
    lastCountRef.current = visible.length;
    const container = containerRef.current;
    if (container) container.scrollTop = container.scrollHeight;
  }, [visible, autoScroll]);

  const counts = useMemo(() => {
    const result: Record<string, number> = { all: 0, info: 0, warning: 0, error: 0, trade: 0 };
    logs.forEach((entry) => {
      if (entry.id <= floorId) return;
      result.all += 1;
      if (result[entry.level] !== undefined) result[entry.level] += 1;
    });
    return result;
  }, [logs, floorId]);

  const clear = () => {
    setFloorId(logs.length ? logs[logs.length - 1].id : 0);
    lastCountRef.current = 0;
  };

  return (
    <Shell>
      <div className="space-y-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-muted">Telemetry</p>
            <h1 className="mt-1.5 flex items-center gap-2 text-2xl font-bold tracking-tight text-fg sm:text-[28px]">
              Live console
              <span
                className={cn(
                  "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider",
                  paused
                    ? "border-warn/25 bg-warn/10 text-warn"
                    : connected
                      ? "border-accent/25 bg-accent/10 text-accent"
                      : "border-danger/25 bg-danger/10 text-danger",
                )}
              >
                <Circle className={cn("h-2 w-2 fill-current", !paused && "animate-pulse")} />
                {paused ? "paused" : connected ? "streaming" : "offline"}
              </span>
            </h1>
            <p className="mt-1 text-sm text-muted">Scanner, scoring, execution and risk events in real time.</p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
              <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} /> Refresh
            </Button>
            <Button variant={paused ? "primary" : "outline"} size="sm" onClick={() => setPaused((value) => !value)}>
              {paused ? <Play className="h-3.5 w-3.5" /> : <Pause className="h-3.5 w-3.5" />}
              {paused ? "Resume" : "Pause"}
            </Button>
          </div>
        </div>

        <Card className="overflow-hidden">
          <div className="flex items-center gap-1.5 border-b border-white/[0.06] bg-white/[0.015] px-4 py-2.5">
            <span className="h-2.5 w-2.5 rounded-full bg-danger/70" />
            <span className="h-2.5 w-2.5 rounded-full bg-warn/70" />
            <span className="h-2.5 w-2.5 rounded-full bg-accent/70" />
            <span className="ml-2 flex items-center gap-1.5 font-mono text-[10px] text-muted">
              <Terminal className="h-3 w-3" /> memeradar@paper · {API_BASE.replace(/^https?:\/\//, "")}
            </span>
            <div className="ml-auto flex items-center gap-3">
              <button
                type="button"
                onClick={() => setAutoScroll((value) => !value)}
                className={cn("font-mono text-[9px] uppercase tracking-wider transition-colors", autoScroll ? "text-accent" : "text-muted hover:text-fg")}
              >
                autoscroll {autoScroll ? "on" : "off"}
              </button>
              <button
                type="button"
                onClick={clear}
                className="flex items-center gap-1 font-mono text-[9px] uppercase tracking-wider text-muted transition-colors hover:text-danger"
              >
                <Trash2 className="h-3 w-3" /> clear
              </button>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 border-b border-white/[0.05] px-4 py-2.5">
            <div className="flex rounded-lg border border-white/[0.07] bg-white/[0.02] p-0.5">
              {LEVELS.map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => setLevel(option)}
                  className={cn(
                    "flex items-center gap-1.5 rounded-md px-2 py-1 font-mono text-[9px] uppercase tracking-wider transition-colors",
                    level === option ? "bg-white/[0.08] text-fg" : "text-muted hover:text-fg",
                  )}
                >
                  {option}
                  <span className={cn("text-[8px]", level === option ? "text-accent" : "text-muted/50")}>
                    {counts[option] ?? 0}
                  </span>
                </button>
              ))}
            </div>
            <div className="relative ml-auto w-full max-w-[280px]">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Grep messages, categories…"
                className="h-8 w-full rounded-lg border border-white/[0.07] bg-white/[0.02] pl-8 pr-3 font-mono text-[11px] text-fg outline-none placeholder:text-muted/60 focus:border-accent/25"
              />
            </div>
          </div>

          <div className="hidden grid-cols-[72px_68px_92px_1fr] gap-2 border-b border-white/[0.05] bg-black/20 px-4 py-1.5 font-mono text-[8px] uppercase tracking-[0.16em] text-muted/60 sm:grid">
            <span>time</span>
            <span>level</span>
            <span>category</span>
            <span>message</span>
          </div>

          <div
            ref={containerRef}
            className="h-[calc(100vh-290px)] min-h-[360px] overflow-y-auto bg-[#04070b]/70"
            onWheel={() => setAutoScroll(false)}
          >
            {visible.length === 0 ? (
              <div className="flex h-full min-h-[300px] flex-col items-center justify-center gap-2 text-center">
                <Terminal className="h-6 w-6 text-muted/50" />
                <p className="text-xs text-muted">
                  {loading ? "Loading log buffer…" : paused ? "Stream paused." : "No events match this filter."}
                </p>
              </div>
            ) : (
              visible.map((entry) => {
                const style = levelStyles[entry.level] || levelStyles.info;
                return (
                  <div
                    key={entry.id}
                    title={entry.meta && Object.keys(entry.meta).length ? JSON.stringify(entry.meta) : undefined}
                    className={cn(
                      "grid grid-cols-[1fr] gap-2 border-b border-white/[0.025] px-4 py-1.5 font-mono text-[11px] transition-colors hover:bg-white/[0.025] sm:grid-cols-[72px_68px_92px_1fr]",
                      style.row,
                    )}
                  >
                    <span className="hidden text-muted/70 sm:block">{fmtTime(entry.ts)}</span>
                    <span className={cn("flex items-center gap-1.5 text-[9px] font-semibold uppercase tracking-wider", style.text)}>
                      <span className={cn("h-1.5 w-1.5 rounded-full", style.dot)} />
                      {entry.level}
                    </span>
                    <span className="hidden truncate text-[9px] uppercase tracking-wider text-muted/60 sm:block">
                      {entry.category}
                    </span>
                    <span className="break-words text-fg/85">
                      <span className="mr-2 text-muted/50 sm:hidden">{fmtTime(entry.ts)}</span>
                      {entry.message}
                    </span>
                  </div>
                );
              })
            )}
            <div className="h-2" />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-white/[0.06] bg-white/[0.015] px-4 py-2 font-mono text-[9px] text-muted/70">
            <span>
              {visible.length} shown · {counts.all} in buffer · {paused ? "stream paused" : "live"}
            </span>
            <span className="flex items-center gap-3">
              <span className="flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-danger" /> error {counts.error}
              </span>
              <span className="flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-warn" /> warning {counts.warning}
              </span>
              <span className="hidden items-center gap-1 sm:flex">
                <Download className="h-3 w-3" /> websocket /ws
              </span>
            </span>
          </div>
        </Card>

        <div className="flex flex-wrap items-center gap-2 text-[10px] text-muted">
          <Badge tone={connected ? "buy" : "danger"}>{connected ? "ws connected" : "ws reconnecting"}</Badge>
          <span>Scrolling disables autoscroll. Clear only hides events for this session.</span>
        </div>
      </div>
    </Shell>
  );
}
