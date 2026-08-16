import { cn } from "@/lib/utils";
import { ButtonHTMLAttributes, forwardRef } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const variantClasses: Record<Variant, string> = {
  primary:
    "bg-teal text-abyss hover:brightness-110 shadow-[0_0_0_1px_rgba(63,199,190,0.4)]",
  secondary:
    "bg-panel-2 text-ink-1 border border-hairline-2 hover:border-teal/50 hover:text-teal",
  ghost: "bg-transparent text-ink-2 hover:text-ink-1 hover:bg-panel-2",
  danger: "bg-crimson/90 text-abyss hover:brightness-110",
};

const sizeClasses: Record<Size, string> = {
  sm: "text-xs px-3 py-1.5 gap-1.5",
  md: "text-sm px-4 py-2 gap-2",
  lg: "text-base px-6 py-3 gap-2.5",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center rounded-lg font-medium tracking-wide transition-all duration-150 disabled:opacity-40 disabled:pointer-events-none whitespace-nowrap",
          variantClasses[variant],
          sizeClasses[size],
          className
        )}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";
