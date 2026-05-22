import { cn } from "@/lib/utils";
import type { ButtonHTMLAttributes } from "react";

const variantClass = {
  primary: "bg-primary text-primary-foreground hover:opacity-90",
  outline: "border border-border bg-card text-foreground hover:bg-gray-100 dark:hover:bg-gray-800",
  ghost: "bg-transparent text-foreground hover:bg-gray-100 dark:hover:bg-gray-800",
};

const sizeClass = {
  sm: "h-9 px-3 text-sm",
  md: "h-10 px-4 text-sm",
  lg: "h-11 px-5 text-base",
};

type ButtonVariant = keyof typeof variantClass;
type ButtonSize = keyof typeof sizeClass;

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
};

export function Button({
  className,
  variant = "primary",
  size = "md",
  type = "button",
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        "inline-flex items-center justify-center rounded-[var(--radius)] font-medium transition-colors disabled:opacity-60 disabled:cursor-not-allowed",
        variantClass[variant],
        sizeClass[size],
        className
      )}
      {...props}
    />
  );
}
