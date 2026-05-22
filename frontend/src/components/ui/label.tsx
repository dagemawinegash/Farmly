import { cn } from "@/lib/utils";
import type { LabelHTMLAttributes } from "react";

type LabelProps = LabelHTMLAttributes<HTMLLabelElement>;

export function Label({ className, ...props }: LabelProps) {
  return <label className={cn("mb-1 block text-sm font-medium text-foreground", className)} {...props} />;
}
