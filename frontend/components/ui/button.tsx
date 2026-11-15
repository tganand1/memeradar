import { forwardRef, type ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

type Variant = "primary" | "ghost" | "outline" | "danger" | "subtle";
type Size = "sm" | "md" | "icon";

const variants: Record<Variant, string> = {
  primary:
    "bg-accent text-black hover:bg-accent/90 shadow-[0_0_24px_-8px_hsl(var(--accent)/0.7)] font-semibold",
  ghost: "bg-transparent text-muted hover:text-fg hover:bg-white/5",
  outline: "border border-white/10 bg-white/[0.02] text-fg hover:bg-white/[0.06] hover:border-white/20",
  danger: "bg-danger/15 text-danger border border-danger/30 hover:bg-danger/25",
  subtle: "bg-white/[0.04] text-fg hover:bg-white/[0.08]",
};

const sizes: Record<Size, string> = {
  sm: "h-8 px-3 text-xs rounded-lg gap-1.5",
  md: "h-10 px-4 text-sm rounded-xl gap-2",
  icon: "h-9 w-9 p-0 rounded-xl justify-center",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "subtle", size = "md", type = "button", ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      className={cn(
        "inline-flex items-center justify-center whitespace-nowrap font-medium transition-all duration-150 disabled:pointer-events-none disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50",
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    />
  ),
);
Button.displayName = "Button";
