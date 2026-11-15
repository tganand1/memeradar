import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

type Tone = "buy" | "watch" | "avoid" | "neutral" | "warn" | "danger" | "info";

const tones: Record<Tone, string> = {
  buy: "border-accent/30 bg-accent/10 text-accent",
  watch: "border-warn/30 bg-warn/10 text-warn",
  avoid: "border-danger/30 bg-danger/10 text-danger",
  neutral: "border-white/10 bg-white/5 text-muted",
  warn: "border-warn/30 bg-warn/10 text-warn",
  danger: "border-danger/30 bg-danger/10 text-danger",
  info: "border-cyan/30 bg-cyan/10 text-cyan",
};

export function Badge({
  tone = "neutral",
  className,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wider",
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}

export function verdictTone(verdict: string): Tone {
  if (verdict === "BUY") return "buy";
  if (verdict === "WATCH") return "watch";
  return "avoid";
}
