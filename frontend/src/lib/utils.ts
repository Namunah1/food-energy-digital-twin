import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function fmtNumber(n: number, digits = 1): string {
  if (Math.abs(n) >= 1e9) return `${(n / 1e9).toFixed(digits)}B`;
  if (Math.abs(n) >= 1e6) return `${(n / 1e6).toFixed(digits)}M`;
  if (Math.abs(n) >= 1e3) return `${(n / 1e3).toFixed(digits)}K`;
  return n.toFixed(digits);
}

export function fmtPct(n: number, digits = 1): string {
  return `${(n * 100).toFixed(digits)}%`;
}

/** Risk color from a food-security ratio (sigma). >=1.0 secure, <0.8 crisis. */
export function riskColor(sigma: number): string {
  if (sigma >= 1.0) return "var(--color-teal)";
  if (sigma >= 0.8) return "var(--color-amber)";
  return "var(--color-crimson)";
}

export function riskLabel(sigma: number): string {
  if (sigma >= 1.0) return "Secure";
  if (sigma >= 0.8) return "Elevated";
  return "Crisis";
}
