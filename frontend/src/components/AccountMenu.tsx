import { useEffect, useRef, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";

export function AccountMenu() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onEsc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onEsc);
    };
  }, [open]);

  if (!user) return null;
  const onAdminRoute = loc.pathname.startsWith("/admin");
  const initial = user.name.slice(0, 1).toUpperCase();

  return (
    <div ref={rootRef} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="h-10 w-10 rounded-full overflow-hidden ring-2 ring-transparent hover:ring-brand-blue/30 focus:ring-brand-blue transition flex items-center justify-center"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Account menu"
      >
        {user.avatar_url ? (
          <img
            src={user.avatar_url}
            alt=""
            referrerPolicy="no-referrer"
            className="h-full w-full object-cover"
          />
        ) : (
          <span className="h-full w-full bg-brand-blue text-white flex items-center justify-center text-base font-semibold">
            {initial}
          </span>
        )}
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 mt-2 w-80 bg-white rounded-xl shadow-xl border border-gray-200 overflow-hidden z-30 animate-[fadeIn_120ms_ease-out]"
        >
          <div className="p-5 bg-gradient-to-br from-brand-blue/5 to-brand-cyan/5 flex flex-col items-center text-center">
            <div className="h-16 w-16 rounded-full overflow-hidden ring-4 ring-white shadow-md mb-3">
              {user.avatar_url ? (
                <img
                  src={user.avatar_url}
                  alt=""
                  referrerPolicy="no-referrer"
                  className="h-full w-full object-cover"
                />
              ) : (
                <span className="h-full w-full bg-brand-blue text-white flex items-center justify-center text-2xl font-semibold">
                  {initial}
                </span>
              )}
            </div>
            <p className="font-semibold text-gray-900 leading-tight">{user.name}</p>
            <p className="text-sm text-gray-500 leading-tight mt-0.5">{user.email}</p>
            {user.role === "admin" && (
              <span className="mt-2 inline-flex items-center px-2 h-5 text-[11px] font-medium rounded-full bg-brand-blue/10 text-brand-blue uppercase tracking-wider">
                Admin
              </span>
            )}
          </div>

          <div className="p-2 flex flex-col">
            {user.role === "admin" && (
              <button
                onClick={() => {
                  setOpen(false);
                  nav(onAdminRoute ? "/" : "/admin");
                }}
                className="text-left px-3 py-2 rounded-md text-sm text-gray-700 hover:bg-gray-100 transition flex items-center gap-3"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="3" />
                  <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1c.5.5 1.2.6 1.8.3.6-.2 1-.8 1-1.5V3a2 2 0 1 1 4 0v.1c0 .7.4 1.3 1 1.5.6.2 1.3.1 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8c.2.6.8 1 1.5 1H21a2 2 0 1 1 0 4h-.1c-.7 0-1.3.4-1.5 1z" />
                </svg>
                {onAdminRoute ? "Back to chat" : "Admin portal"}
              </button>
            )}
            <button
              onClick={async () => {
                setOpen(false);
                await logout();
                nav("/login");
              }}
              className="text-left px-3 py-2 rounded-md text-sm text-gray-700 hover:bg-gray-100 transition flex items-center gap-3"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
              Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
