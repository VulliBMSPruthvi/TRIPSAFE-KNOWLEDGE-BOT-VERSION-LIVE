import { NavLink, Outlet } from "react-router-dom";
import type { ReactNode } from "react";
import { AppHeader } from "@/components/AppHeader";

const tabs: Array<{ to: string; label: string; icon: ReactNode }> = [
  { to: "/admin", label: "Dashboard", icon: <DotsIcon /> },
  { to: "/admin/users", label: "Users", icon: <UsersIcon /> },
  { to: "/admin/chats", label: "Chat Logs", icon: <ChatIcon /> },
  { to: "/admin/knowledge", label: "Knowledge Base", icon: <FileIcon /> },
  { to: "/admin/prompts", label: "System Prompt", icon: <PromptIcon /> },
  { to: "/admin/integrations", label: "Integrations", icon: <GearIcon /> },
  { to: "/admin/activity", label: "Activity Log", icon: <ListIcon /> },
];

export function AdminLayout() {
  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <AppHeader />
      <div className="flex-1 flex">
        <aside className="w-60 border-r border-gray-200 bg-white p-4 hidden md:flex flex-col gap-1 shrink-0">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-400 px-2 py-2">
            Admin Portal
          </h2>
          {tabs.map((t) => (
            <NavLink
              key={t.to}
              to={t.to}
              end={t.to === "/admin"}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-md text-sm transition ${
                  isActive
                    ? "bg-brand-blue/10 text-brand-blue font-medium"
                    : "text-gray-700 hover:bg-gray-100"
                }`
              }
            >
              <span className="text-gray-400">{t.icon}</span>
              {t.label}
            </NavLink>
          ))}
        </aside>

        <main className="flex-1 p-6 max-w-6xl w-full mx-auto">
          {/* Mobile tabs */}
          <div className="md:hidden mb-4 overflow-x-auto -mx-6 px-6 scrollbar-thin">
            <div className="flex gap-2">
              {tabs.map((t) => (
                <NavLink
                  key={t.to}
                  to={t.to}
                  end={t.to === "/admin"}
                  className={({ isActive }) =>
                    `whitespace-nowrap px-3 py-2 rounded-md text-sm border transition ${
                      isActive
                        ? "bg-brand-blue text-white border-brand-blue"
                        : "bg-white text-gray-700 border-gray-200"
                    }`
                  }
                >
                  {t.label}
                </NavLink>
              ))}
            </div>
          </div>
          <Outlet />
        </main>
      </div>
    </div>
  );
}

// ── Minimal inline icons (SVG, design-system gray-400) ─────────────
function DotsIcon() { return <Svg><path d="M4 6h16M4 12h16M4 18h10" /></Svg>; }
function UsersIcon() { return <Svg><circle cx="9" cy="8" r="3"/><circle cx="17" cy="9" r="2.5"/><path d="M3 19c0-3 3-5 6-5s6 2 6 5"/><path d="M15 19c0-2 2-3.5 4-3.5"/></Svg>; }
function ChatIcon() { return <Svg><path d="M4 5h16v10H8l-4 4V5z"/></Svg>; }
function FileIcon() { return <Svg><path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5"/></Svg>; }
function PromptIcon() { return <Svg><path d="M4 6h16M4 12h10M4 18h16"/></Svg>; }
function GearIcon() { return <Svg><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1c.5.5 1.2.6 1.8.3.6-.2 1-.8 1-1.5V3a2 2 0 1 1 4 0v.1c0 .7.4 1.3 1 1.5.6.2 1.3.1 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8c.2.6.8 1 1.5 1H21a2 2 0 1 1 0 4h-.1c-.7 0-1.3.4-1.5 1z"/></Svg>; }
function ListIcon() { return <Svg><path d="M8 6h12M8 12h12M8 18h12"/><circle cx="4" cy="6" r="1"/><circle cx="4" cy="12" r="1"/><circle cx="4" cy="18" r="1"/></Svg>; }

function Svg({ children }: { children: ReactNode }) {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {children}
    </svg>
  );
}
