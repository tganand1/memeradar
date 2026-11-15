"use client";

import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "animate-shimmer rounded-lg bg-[linear-gradient(110deg,rgba(255,255,255,0.04),45%,rgba(255,255,255,0.09),55%,rgba(255,255,255,0.04))] bg-[length:200%_100%]",
        className,
      )}
    />
  );
}
