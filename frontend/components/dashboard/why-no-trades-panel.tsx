import { ChevronRight, Target, Zap, AlertTriangle } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { useLiveStore } from "@/lib/store";
import { fmtUsd, fmtPct } from "@/lib/format";
import { cn } from "@/lib/utils";

export function WhyNoTradesPanel() {
  const snapshot = useLiveStore((state) => state.snapshot);

  const reasons: { icon: React.ReactNode; label: string; detail: string }[] = [];

  if (!snapshot?.bot_enabled) {
    reasons.push({
      icon: <Play className="h-3.5 w-3.5" />,
      label: "Bot paused",
      detail: "No new entries or automated exits are being taken. Open positions can still be closed manually.",
    });
  }

  const positions = snapshot?.positions || [];
  if (positions.length > 0) {
    reasons.push({
      icon: <Target className="h-3.5 w-3.5" />,
      label: "Open positions",
      detail: `${positions.length} active position(s) currently holding capital.`,
    });
  }

  const tokens = snapshot?.tokens || [];
  if (tokens.length > 0) {
    const buyTokens = tokens.filter(
      (t) => t.verdict === "BUY" || t.final_score >= 55 || t.decision === "BUY"
    );
    if (buyTokens.length > 0) {
      reasons.push({
        icon: <Zap className="h-3.5 w-3.5" />,
        label: "Ready to enter",
        detail: `${buyTokens.length} token(s) cleared the buy threshold but had no open slots.`,
      });
    } else {
      reasons.push({
        icon: <AlertTriangle className="h-3.5 w-3.5" />,
        label: "No buy signals",
        detail: `No token has reached the ${fmtUsd(snapshot?.config?.strategy?.min_score_buy ?? 55)} buy threshold yet.`,
      });
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-3">
        <div>
          <CardTitle className="flex items-center gap-2 text-sm">
            <AlertTriangle className="h-4 w-4 text-amber" />
            Why no trades?
          </CardTitle>
          <p className="mt-0.5 text-[11px] text-muted">
            {reasons.length === 0
              ? "The bot is actively scanning and ready to trade. Check back soon."
              : "Common reasons trades haven't fired yet:"}
          </p>
        </div>
        <Link
          href="/analytics"
          className="rounded-lg border border-white/10 px-2.5 py-1.5 text-[11px] text-muted transition-colors hover:bg-white/[0.05] hover:text-fg"
        >
          See analytics <ChevronRight className="h-3 w-3" />
        </Link>
      </CardHeader>
      <div className="p-4">
        {reasons.length === 0 ? (
          <p className="text-[11px] text-muted">The bot is actively scanning and ready to trade. Check back soon.</p>
        ) : (
          <div className="space-y-2">
            {reasons.map((item, idx) => (
              <div
                key={idx}
                className="flex items-start gap-2.5 rounded-xl border border-white/[0.04] bg-white/[0.015] px-3 py-2.5"
              >
                <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-white/5">
                  {item.icon}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="font-mono text-[11px] font-semibold text-fg">{item.label}</p>
                  <p className="truncate text-[9px] text-muted">{item.detail}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}