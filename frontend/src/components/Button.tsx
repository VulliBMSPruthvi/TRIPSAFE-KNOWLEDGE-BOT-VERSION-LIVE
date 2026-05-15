import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  leftIcon?: ReactNode;
}

const variants: Record<Variant, string> = {
  primary:
    "bg-brand-blue text-white shadow-btn hover:bg-brand-navy focus-visible:outline-brand-blue",
  secondary:
    "bg-white text-brand-blue border border-gray-200 hover:bg-gray-50 focus-visible:outline-brand-blue",
  ghost:
    "bg-transparent text-gray-700 hover:bg-gray-100 focus-visible:outline-brand-blue",
  danger:
    "bg-danger text-white shadow-btn hover:opacity-90 focus-visible:outline-danger",
};

const sizes: Record<Size, string> = {
  sm: "h-8 px-3 text-sm rounded-sm",
  md: "h-10 px-4 text-base rounded-md",
  lg: "h-12 px-6 text-base rounded-md",
};

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  leftIcon,
  disabled,
  className = "",
  children,
  ...rest
}: Props) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-2 font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50 disabled:cursor-not-allowed ${variants[variant]} ${sizes[size]} ${className}`}
    >
      {loading ? (
        <span className="h-4 w-4 inline-block border-2 border-current border-r-transparent rounded-full animate-spin" />
      ) : leftIcon ? (
        <span className="inline-flex">{leftIcon}</span>
      ) : null}
      <span>{children}</span>
    </button>
  );
}
