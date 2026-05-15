import logoHeader from "@/assets/TripSafe-Logo-header.png";
import logoFull from "@/assets/TripSafe-Logo.png";
import logoWhite from "@/assets/TripSafe-Logo-white.png";
import logoMark from "@/assets/TripSafe logo-01.png";

type Variant = "header" | "full" | "white" | "mark";

export function Logo({
  variant = "header",
  className = "h-8 w-auto",
  alt = "TripSafe",
}: {
  variant?: Variant;
  className?: string;
  alt?: string;
}) {
  const src =
    variant === "white"
      ? logoWhite
      : variant === "full"
        ? logoFull
        : variant === "mark"
          ? logoMark
          : logoHeader;
  return <img src={src} alt={alt} className={className} />;
}
