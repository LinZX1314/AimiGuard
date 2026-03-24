import type { VariantProps } from "class-variance-authority"
import { cva } from "class-variance-authority"

export { default as Button } from "./Button.vue"

export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/18 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground shadow-[0_10px_24px_hsl(var(--primary)/0.16)] hover:bg-primary/92 hover:shadow-[0_12px_28px_hsl(var(--primary)/0.22)]",
        destructive:
          "bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/92",
        outline:
          "border border-border/75 bg-gradient-to-br from-card/86 via-secondary/18 to-muted/22 text-foreground shadow-[0_8px_18px_rgba(67,84,109,0.08)] hover:border-primary/24 hover:bg-secondary/42 hover:text-foreground",
        secondary:
          "border border-border/70 bg-gradient-to-br from-secondary/88 to-muted/36 text-secondary-foreground shadow-[0_8px_18px_rgba(67,84,109,0.08)] hover:bg-secondary/96",
        ghost:
          "text-foreground/82 hover:bg-secondary/48 hover:text-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2",
        xs: "h-7 rounded-md px-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-10 rounded-lg px-8",
        icon: "h-9 w-9",
        "icon-sm": "size-8",
        "icon-lg": "size-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
)

export type ButtonVariants = VariantProps<typeof buttonVariants>
