"use client";

import { BarChart3, History, Radar, Settings2, TerminalSquare } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { TokenDrawer } from "@/components/token-drawer";
import { Topbar } from "@/components/shell/topbar";
import { Sidebar } from "@/components/shell/sidebar";
import { cn } from "@/lib/utils";

const mobileNav = [
  { href: "/", label: "Radar", icon: Radar },
  { href: "/history", label: "History", icon: History },
  { href: "/analytics", label: "Stats", icon: BarChart3 },
  { href: "/console", label: "Console", icon: TerminalSquare },
  { href: "/settings", label: "Config", icon: Settings2 },
];

function MobileNav() {
  const pathname = usePathname();
  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-white/[0.07] bg-[#060a10]/92 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl lg:hidden">
      <div className="grid grid-cols-5">
        {mobileNav.map((item) => {
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex flex-col items-center gap-1 py-2.5 text-[9px] font-medium uppercase tracking-wider transition-colors",
                active ? "text-accent" : "text-muted",
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

export function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative z-10 flex min-h-screen">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main className="mx-auto w-full max-w-[1680px] flex-1 px-4 pb-24 pt-5 sm:px-6 lg:pb-10">{children}</main>
      </div>
      <TokenDrawer />
      <MobileNav />
    </div>
  );
}
