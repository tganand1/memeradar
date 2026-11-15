"use client";

import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export const TooltipProvider = TooltipPrimitive.Provider;

export function Tooltip({
  label,
  children,
  side = "top",
  className,
}: {
  label: ReactNode;
  children: ReactNode;
  side?: "top" | "right" | "bottom" | "left";
  className?: string;
}) {
  if (!label) return <>{children}</>;
  return (
    <TooltipPrimitive.Root delayDuration={180}>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          side={side}
          sideOffset={6}
          className={cn(
            "z-[120] max-w-xs rounded-lg border border-white/10 bg-[#0b1018]/95 px-2.5 py-1.5 text-xs text-fg shadow-xl backdrop-blur",
            className,
          )}
        >
          {label}
          <TooltipPrimitive.Arrow className="fill-[#0b1018]" />
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}
