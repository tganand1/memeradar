"use client";

import { ArrowUpRight, Terminal } from "lucide-react";
import Link from "next/link";

import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { fmtClock } from "@/lib/format";
import { useLiveStore } from "@/lib/store";
import { cn } from "@/lib/utils";

const levelColor: Record<string, string> = {
  trade: "bg-accent",
  info: "bg-cyan/70",
  warning: "bg-warn",
  error: "bg-danger",
};

function compactMessage(message: string): string {
  return message
    .replace(/dY["'`´]?[^ ]*/g, "")
    .replace(/[�]+/g, "-")
    .replace(/\s+/g, " ")
    .trim();
}

export function ActivityPanel() {
  const logs = useLiveStore((state) => state.snapshot?.logs || []);
  const recent = logs.slice(-14).reverse();

  return (
    <Card className="overflow-hidden">
      <CardHeader className="items-center pb-3">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Terminal className="h-3.5 w-3.5 text-muted" /> Live activity
          </CardTitle>
          <p className="mt-0.5 text-[11px] text-muted">Scanner, risk and execution events</p>
        </div>
        <Link
          href="/console"
          className="inline-flex items-center gap-1 text-[11px] text-muted transition-colors hover:text-fg"
        >
          Console <ArrowUpRight className="h-3 w-3" />
        </Link>
      </CardHeader>
      <div className="max-h-[330px] overflow-y-auto border-t border-white/[0.05]">
        {recent.length === 0 ? (
          <p className="px-5 py-8 text-center text-xs text-muted">Waiting for activity…</p>
        ) : (
          recent.map((entry) => (
            <div
              key={entry.id}
              className="flex items-start gap-2.5 border-b border-white/[0.03] px-4 py-2 last:border-0"
            >
              <span className={cn("mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full", levelColor[entry.level] || "bg-muted")} />
              <div className="min-w-0 flex-1">
                <p className="line-clamp-2 text-[11px] leading-relaxed text-fg/90">{compactMessage(entry.message)}</p>
                <p className="mt-0.5 flex items-center gap-2 font-mono text-[9px] uppercase tracking-wider text-muted/60">
                  <span>{entry.category}</span>
                  <span>·</span>
                  <span>{fmtClock(entry.ts)}</span>
                </p>
              </div>
            </div>
          ))
        )}
      </div>
    </Card>
  );
}
