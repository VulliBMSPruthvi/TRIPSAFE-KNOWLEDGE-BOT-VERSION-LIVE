import { useEffect, useState } from "react";
import { api, type ChatMessage } from "@/api/client";
import { Card } from "@/components/Card";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Spinner } from "@/components/Spinner";
import { Input } from "@/components/Input";

interface AdminSession {
  id: string;
  user_id: string;
  user_email: string;
  user_name: string;
  started_at: string;
  last_message_at: string;
  message_count: number;
}

export function ChatLogsPage() {
  const [sessions, setSessions] = useState<AdminSession[]>([]);
  const [selectedSession, setSelectedSession] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [searchResults, setSearchResults] = useState<Awaited<ReturnType<typeof api.searchChats>> | null>(null);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    api.adminSessions().then(setSessions).finally(() => setLoading(false));
  }, []);

  const loadSession = async (id: string) => {
    setSelectedSession(id);
    setMessages([]);
    const msgs = await api.adminSessionMessages(id);
    setMessages(msgs);
  };

  const doSearch = async () => {
    if (!search.trim()) return;
    setSearching(true);
    try {
      setSearchResults(await api.searchChats(search.trim()));
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-gray-900">Chat Logs</h1>
        <p className="text-sm text-gray-500 mt-1">Browse every conversation and search across messages.</p>
      </div>

      <Card>
        <div className="flex gap-2">
          <div className="flex-1">
            <Input
              placeholder="Search across all chat messages…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void doSearch()}
            />
          </div>
          <Button onClick={() => void doSearch()} loading={searching}>Search</Button>
          {searchResults && (
            <Button variant="ghost" onClick={() => { setSearchResults(null); setSearch(""); }}>
              Clear
            </Button>
          )}
        </div>
        {searchResults && (
          <div className="mt-4 space-y-2 max-h-80 overflow-y-auto scrollbar-thin">
            {searchResults.length === 0 ? (
              <p className="text-sm text-gray-500">No matches.</p>
            ) : (
              searchResults.map((r) => (
                <div key={r.message_id} className="border border-gray-200 rounded-md p-3 text-sm">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge tone={r.role === "user" ? "neutral" : "brand"}>{r.role}</Badge>
                    <span className="text-xs text-gray-500">{r.user_email}</span>
                    <span className="text-xs text-gray-400 ml-auto">{new Date(r.created_at).toLocaleString()}</span>
                  </div>
                  <p className="text-gray-700 line-clamp-3">{r.content}</p>
                  <button
                    className="mt-1 text-xs text-brand-blue hover:underline"
                    onClick={() => void loadSession(r.session_id)}
                  >
                    Open session →
                  </button>
                </div>
              ))
            )}
          </div>
        )}
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card padded={false} className="lg:col-span-1 max-h-[600px] overflow-y-auto scrollbar-thin">
          <div className="p-4 border-b border-gray-100">
            <h3 className="text-sm font-semibold text-gray-900">Sessions</h3>
          </div>
          {loading ? (
            <div className="p-10 flex justify-center"><Spinner /></div>
          ) : (
            <ul className="divide-y divide-gray-100">
              {sessions.map((s) => (
                <li key={s.id}>
                  <button
                    onClick={() => void loadSession(s.id)}
                    className={`w-full text-left p-3 hover:bg-gray-50 transition ${
                      selectedSession === s.id ? "bg-brand-blue/5" : ""
                    }`}
                  >
                    <div className="text-sm font-medium text-gray-900 truncate">{s.user_email}</div>
                    <div className="text-xs text-gray-500 mt-0.5 flex gap-2">
                      <span>{s.message_count} msgs</span>
                      <span>•</span>
                      <span>{new Date(s.last_message_at).toLocaleString()}</span>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card padded={false} className="lg:col-span-2 max-h-[600px] flex flex-col">
          <div className="p-4 border-b border-gray-100 flex justify-between items-center">
            <h3 className="text-sm font-semibold text-gray-900">Transcript</h3>
            {selectedSession && (() => {
              const s = sessions.find((x) => x.id === selectedSession);
              if (!s) return null;
              return (
                <a
                  href={api.exportUserChats(s.user_id)}
                  className="text-xs text-brand-blue hover:underline"
                >
                  Export this user's CSV
                </a>
              );
            })()}
          </div>
          <div className="flex-1 overflow-y-auto scrollbar-thin p-4 space-y-3">
            {!selectedSession ? (
              <p className="text-sm text-gray-400 text-center py-12">Pick a session on the left.</p>
            ) : (
              messages.map((m) => (
                <div key={m.id} className="flex gap-2">
                  <Badge tone={m.role === "user" ? "neutral" : "brand"}>{m.role}</Badge>
                  <div className="flex-1 text-sm text-gray-700 whitespace-pre-wrap">
                    {m.content}
                  </div>
                </div>
              ))
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
