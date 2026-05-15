import { useNavigate } from "react-router-dom";
import { Logo } from "./Logo";
import { AccountMenu } from "./AccountMenu";
import { useAuth } from "@/auth/AuthContext";

interface Props {
  title?: string;
  subtitle?: string;
  variant?: "bordered" | "flat";
}

export function AppHeader({
  title = "TripSafe AI Assistant",
  subtitle = "Your TripSafe expert",
  variant = "bordered",
}: Props) {
  const nav = useNavigate();
  const { user } = useAuth();

  return (
    <header
      className={`h-20 bg-white flex items-center px-4 sm:px-6 sticky top-0 z-20 ${
        variant === "bordered" ? "border-b border-gray-200" : ""
      }`}
    >
      <button
        onClick={() => nav("/")}
        className="flex items-center gap-3"
        aria-label="Home"
      >
        <Logo variant="full" className="h-14 sm:h-16 w-auto block" />
      </button>

      <div className="hidden md:flex flex-col leading-tight ml-4 pl-4 border-l border-gray-200">
        <span className="text-base font-semibold text-gray-900">{title}</span>
        <span className="text-xs text-gray-500">{subtitle}</span>
      </div>

      <div className="flex-1" />

      {user && (
        <div className="flex items-center gap-3">
          <div className="hidden sm:flex flex-col leading-tight text-right">
            <span className="text-sm font-medium text-gray-900">{user.name}</span>
            <span className="text-[11px] text-gray-500">
              {user.role === "admin" ? "Administrator" : "User"}
            </span>
          </div>
          <AccountMenu />
        </div>
      )}
    </header>
  );
}
