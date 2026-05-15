export function Spinner({ size = "md" }: { size?: "sm" | "md" | "lg" }) {
  const px = size === "sm" ? "h-4 w-4" : size === "md" ? "h-6 w-6" : "h-10 w-10";
  return (
    <span
      role="status"
      className={`inline-block ${px} border-[3px] border-brand-blue/30 border-t-brand-blue rounded-full animate-spin`}
    />
  );
}
