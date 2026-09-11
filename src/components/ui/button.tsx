import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap font-semibold uppercase tracking-wider border transition-[color,background-color,border-color,box-shadow,transform] duration-[var(--motion-quick)] ease-[var(--ease-out)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-40 active:scale-[0.96]",
  {
    variants: {
      variant: {
        primary:
          "bg-accent text-accent-fg border-accent hover:bg-accent-hover hover:border-accent-hover hover:-translate-y-px hover:shadow-[var(--shadow-accent)]",
        secondary:
          "bg-transparent text-fg border-fg hover:bg-fg hover:text-ink",
        ghost:
          "bg-transparent text-fg border-transparent px-0 hover:text-accent",
        inverse:
          "bg-inverse text-ink border-inverse hover:bg-transparent hover:text-inverse",
        outlineInverse:
          "bg-transparent text-inverse/80 border-inverse/25 hover:border-inverse hover:bg-inverse/10 hover:text-inverse",
      },
      size: {
        default: "min-h-11 rounded-full px-8 py-3 text-sm",
        sm: "min-h-9 rounded-full px-5 py-2 text-xs",
        lg: "min-h-12 rounded-full px-11 py-4 text-base",
      },
    },
    defaultVariants: { variant: "primary", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size }), className)}
        ref={ref}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";
