"use client";

import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";
import { gradientFor } from "@/lib/format";

export function TokenAvatar({
  symbol,
  imageUrl,
  size = 36,
  className,
}: {
  symbol: string;
  imageUrl?: string | null;
  size?: number;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [imageUrl]);

  const style = { width: size, height: size, background: gradientFor(symbol || "?") };

  return (
    <div
      className={cn(
        "relative shrink-0 overflow-hidden rounded-xl border border-white/10 text-[10px] font-bold text-black/80",
        className,
      )}
      style={style}
    >
      {!failed && imageUrl ? (
        <img
          src={imageUrl}
          alt={symbol}
          loading="lazy"
          referrerPolicy="no-referrer"
          className="h-full w-full object-cover"
          onError={() => setFailed(true)}
        />
      ) : (
        <span className="flex h-full w-full items-center justify-center font-mono uppercase">
          {(symbol || "?").slice(0, 2)}
        </span>
      )}
    </div>
  );
}
