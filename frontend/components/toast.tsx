"use client";

import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { cn } from "@/lib/utils";

type ToastVariant = "success" | "error" | "info" | "warning";

export interface ToastInput {
  title: string;
  description?: string;
  variant?: ToastVariant;
  duration?: number;
}

interface ToastItem extends ToastInput {
  id: number;
}

type ToastFn = (toast: ToastInput) => void;

const ToastContext = createContext<{ toast: ToastFn } | null>(null);

const icons = {
  success: CheckCircle2,
  error: XCircle,
  info: Info,
  warning: AlertTriangle,
};

const tones: Record<ToastVariant, string> = {
  success: "border-accent/30 text-accent",
  error: "border-danger/30 text-danger",
  info: "border-cyan/30 text-cyan",
  warning: "border-warn/30 text-warn",
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const counter = useRef(0);

  const dismiss = useCallback((id: number) => {
    setItems((current) => current.filter((item) => item.id !== id));
  }, []);

  const toast = useCallback<ToastFn>(
    (input) => {
      counter.current += 1;
      const id = counter.current;
      const item: ToastItem = { variant: "info", duration: 4200, ...input, id };
      setItems((current) => [item, ...current].slice(0, 5));
      window.setTimeout(() => dismiss(id), item.duration);
    },
    [dismiss],
  );

  const value = useMemo(() => ({ toast }), [toast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed right-4 top-4 z-[150] flex w-[360px] max-w-[calc(100vw-2rem)] flex-col gap-2">
        <AnimatePresence initial={false}>
          {items.map((item) => {
            const variant = item.variant || "info";
            const Icon = icons[variant];
            return (
              <motion.div
                key={item.id}
                layout
                initial={{ opacity: 0, x: 30, scale: 0.96 }}
                animate={{ opacity: 1, x: 0, scale: 1 }}
                exit={{ opacity: 0, x: 30, scale: 0.96 }}
                transition={{ type: "spring", stiffness: 380, damping: 32 }}
                className={cn(
                  "pointer-events-auto relative overflow-hidden rounded-xl border bg-[#0a0f16]/92 p-3.5 pl-4 shadow-2xl backdrop-blur-xl",
                  tones[variant],
                )}
              >
                <div className="flex items-start gap-3">
                  <Icon className="mt-0.5 h-4 w-4 shrink-0" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-fg">{item.title}</p>
                    {item.description ? (
                      <p className="mt-0.5 text-xs leading-relaxed text-muted">{item.description}</p>
                    ) : null}
                  </div>
                  <button
                    type="button"
                    onClick={() => dismiss(item.id)}
                    className="shrink-0 rounded p-0.5 text-muted transition-colors hover:text-fg"
                    aria-label="Dismiss"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastFn {
  const context = useContext(ToastContext);
  if (!context) {
    return () => undefined;
  }
  return context.toast;
}
