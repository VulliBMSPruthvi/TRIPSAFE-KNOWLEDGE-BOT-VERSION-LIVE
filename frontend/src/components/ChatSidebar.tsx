import { useEffect, useState } from "react";
import { api, type ChatSession } from "@/api/client";

interface Props {
  open: boolean;
  onClose: () => void;
  activeSessionId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  refreshKey: number;
}

/**
 * Responsive history drawer.
 *  - md+: pushes the chat content (slides width 0 ↔ 18rem).
 *  - sm:  overlays the chat with a backdrop (slides translateX).
 */
export function ChatSidebar({
  open,
  onClose,
  activeSessionId,
  onSelect,
  onNew,
  refreshKey,
}: Props) {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    api
      .listSessions()
      .then((s) => !cancelled && setSessions(s))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  return (
    <>
      {/* Mobile backdrop */}
      {open && (
        <button
          onClick={onClose}
          aria-label="Close history"
          className="fixed inset-0 bg-gray-900/40 z-30 md:hidden"
        />
      )}

      <aside
        aria-hidden={!open}
        className={`
          fixed md:relative top-0 left-0 h-full bg-white border-r border-gray-200 z-40 md:z-auto
          flex flex-col overflow-hidden
          transition-all duration-300 ease-in-out
          ${open
            ? "translate-x-0 w-[18rem]"
            : "-translate-x-full md:translate-x-0 md:w-0 w-[18rem]"}
        `}
      >
        <div className="w-[18rem] flex flex-col h-full min-w-0">
          <div className="p-3 flex items-center gap-2 border-b border-gray-100">
            <button
              onClick={onNew}
              className="flex-1 h-10 rounded-md bg-brand-blue text-white font-medium flex items-center justify-center gap-2 shadow-btn hover:bg-brand-navy transition"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              New chat
            </button>
            <button
              onClick={onClose}
              aria-label="Hide history"
              className="h-10 w-10 rounded-md text-gray-500 hover:bg-gray-100 hover:text-gray-700 transition flex items-center justify-center shrink-0"
              title="Hide history"
            >
              <ChevronLeftIcon />
            </button>
          </div>

          <div className="px-3 py-2 text-[11px] uppercase tracking-wider text-gray-400 font-semibold">
            Recent
          </div>

          <div className="flex-1 overflow-y-auto scrollbar-thin px-2 pb-3">
            {loading ? (
              <div className="px-3 py-4 text-sm text-gray-400">Loading…</div>
            ) : sessions.length === 0 ? (
              <div className="px-3 py-4 text-sm text-gray-400">
                No conversations yet. Ask something to start.
              </div>
            ) : (
              <ul className="space-y-0.5">
                {sessions.map((s) => {
                  const isActive = s.id === activeSessionId;
                  return (
                    <li key={s.id}>
                      <button
                        onClick={() => onSelect(s.id)}
                        className={`w-full text-left px-3 py-2 rounded-md text-sm transition flex flex-col gap-0.5 ${
                          isActive
                            ? "bg-brand-blue/10 text-brand-blue"
                            : "text-gray-700 hover:bg-gray-100"
                        }`}
                      >
                        <span className="font-medium truncate">{formatTitle(s)}</span>
                        <span className="text-[11px] text-gray-400">
                          {formatTime(s.last_message_at)} · {s.message_count} msg
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      </aside>
    </>
  );
}

function ChevronLeftIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="15 18 9 12 15 6" />
    </svg>
  );
}

function formatTitle(s: ChatSession): string {
  const d = new Date(s.started_at);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatTime(iso: string): string {
  const ts = new Date(iso).getTime();
  const diff = Date.now() - ts;
  const min = Math.floor(diff / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  return new Date(iso).toLocaleDateString();
}
