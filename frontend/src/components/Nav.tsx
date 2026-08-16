"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Radar } from "lucide-react";

const LINKS = [
  { href: "/console", label: "Experiment Studio" },
  { href: "/countries", label: "Countries" },
  { href: "/policy-lab", label: "Policy Lab" },
];

export function Nav() {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-50 border-b border-hairline bg-abyss/85 backdrop-blur-md">
      <div className="mx-auto max-w-[1400px] px-6 h-16 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2.5 group">
          <Radar size={20} className="text-teal" strokeWidth={1.75} />
          <span className="font-display text-[15px] font-semibold tracking-tight">
            Systemic Risk Observatory
          </span>
        </Link>
        <nav className="hidden md:flex items-center gap-1">
          {LINKS.map((l) => {
            const active = pathname === l.href || pathname.startsWith(l.href + "/");
            return (
              <Link
                key={l.href}
                href={l.href}
                className={cn(
                  "px-3.5 py-2 rounded-lg text-sm transition-colors",
                  active
                    ? "text-ink-1 bg-panel-2"
                    : "text-ink-2 hover:text-ink-1 hover:bg-panel-2/60"
                )}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>
        <div className="flex items-center gap-2 font-mono text-[11px] text-ink-3">
          <span className="w-1.5 h-1.5 rounded-full bg-teal animate-pulse" />
          MODEL LIVE
        </div>
      </div>
    </header>
  );
}
