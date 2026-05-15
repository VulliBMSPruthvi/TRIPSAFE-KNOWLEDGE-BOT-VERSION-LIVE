import { useEffect, useState } from "react";
import { api, type DashboardStats } from "@/api/client";
import { Card } from "@/components/Card";
import { Badge } from "@/components/Badge";
import { Spinner } from "@/components/Spinner";

export function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.dashboard().then(setStats).catch((e) => setErr(String(e)));
  }, []);

  if (err) return <Card><p className="text-danger">{err}</p></Card>;
  if (!stats) return <div className="py-12 flex justify-center"><Spinner size="lg" /></div>;

  const tiles = [
    { label: "Total users", value: stats.total_users, tone: "brand" as const },
    { label: "Active users", value: stats.active_users, tone: "success" as const },
    { label: "Chats today", value: stats.chats_today, tone: "info" as const },
    { label: "Total chats", value: stats.total_chats, tone: "neutral" as const },
    { label: "Active sessions (30 min)", value: stats.active_sessions_30m, tone: "warning" as const },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-gray-900">Dashboard</h1>
        <p className="text-sm text-gray-500 mt-1">Health of the TripSafe Knowledge Bot in real time.</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {tiles.map((t) => (
          <Card key={t.label} className="flex flex-col gap-2">
            <span className="text-xs uppercase tracking-wider text-gray-500">{t.label}</span>
            <span className="text-3xl font-semibold text-gray-900">{t.value}</span>
          </Card>
        ))}
      </div>

      <Card>
        <h3 className="text-xl font-semibold text-gray-900 mb-3">Knowledge Base</h3>
        <div className="flex flex-wrap items-center gap-4">
          <Badge tone={stats.rag_index_loaded ? "success" : "warning"}>
            {stats.rag_index_loaded ? "Index loaded" : "Index not built"}
          </Badge>
          <span className="text-sm text-gray-600">
            {stats.rag_chunk_count} chunks indexed
          </span>
          {stats.rag_loaded_at && (
            <span className="text-xs text-gray-400">
              loaded {new Date(stats.rag_loaded_at).toLocaleString()}
            </span>
          )}
        </div>
      </Card>

      <Card>
        <h3 className="text-xl font-semibold text-gray-900 mb-3">Recent activity</h3>
        <ul className="divide-y divide-gray-100">
          {stats.recent_activity.map((a) => (
            <li key={a.id} className="py-2 flex items-center gap-3">
              <Badge tone="neutral">{a.action_type}</Badge>
              <span className="text-sm text-gray-700 truncate flex-1">
                {a.user_email ?? "—"}
              </span>
              <span className="text-xs text-gray-400">
                {new Date(a.created_at).toLocaleString()}
              </span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
