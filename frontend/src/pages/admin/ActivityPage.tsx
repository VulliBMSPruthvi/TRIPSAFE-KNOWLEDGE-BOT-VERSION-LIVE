import { useEffect, useState } from "react";
import { api, type ActivityPage as ActivityPageT } from "@/api/client";
import { Card } from "@/components/Card";
import { Button } from "@/components/Button";
import { Badge } from "@/components/Badge";
import { Spinner } from "@/components/Spinner";

const KNOWN_ACTIONS = [
  "LOGIN", "LOGIN_FAILED", "LOGOUT", "SIGNUP", "REFRESH",
  "CHAT", "FILE_UPLOAD", "FILE_DELETE", "INDEX_REBUILD",
  "PROMPT_UPDATE", "MODEL_CHANGE", "ROLE_CHANGE",
  "USER_DEACTIVATE", "USER_REACTIVATE", "OAUTH_CONFIG_UPDATE",
];

export function ActivityPage() {
  const [data, setData] = useState<ActivityPageT | null>(null);
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .activity({ page, action_type: filter || undefined })
      .then(setData)
      .finally(() => setLoading(false));
  }, [page, filter]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-gray-900">Activity Log</h1>
        <p className="text-sm text-gray-500 mt-1">
          Every meaningful action across the platform — fully auditable.
        </p>
      </div>

      <Card padded={false}>
        <div className="p-4 border-b border-gray-100 flex gap-2 items-center flex-wrap">
          <select
            value={filter}
            onChange={(e) => { setPage(1); setFilter(e.target.value); }}
            className="h-9 px-2 rounded-md border border-gray-200 text-sm bg-white"
          >
            <option value="">All actions</option>
            {KNOWN_ACTIONS.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
          {data && (
            <span className="text-xs text-gray-500 ml-auto">
              {data.total} total · page {data.page}
            </span>
          )}
        </div>

        {loading ? (
          <div className="p-10 flex justify-center"><Spinner /></div>
        ) : !data || data.rows.length === 0 ? (
          <p className="p-6 text-sm text-gray-500">No matching entries.</p>
        ) : (
          <ul className="divide-y divide-gray-100">
            {data.rows.map((r) => (
              <li key={r.id} className="px-4 py-3 flex items-start gap-3">
                <Badge tone="neutral">{r.action_type}</Badge>
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-gray-900">{r.user_email ?? "—"}</div>
                  {r.extra && Object.keys(r.extra).length > 0 && (
                    <details className="text-xs text-gray-500 mt-0.5">
                      <summary className="cursor-pointer">details</summary>
                      <pre className="mt-1 bg-gray-50 p-2 rounded text-[11px] overflow-x-auto">
                        {JSON.stringify(r.extra, null, 2)}
                      </pre>
                    </details>
                  )}
                </div>
                <div className="text-right text-xs text-gray-400 whitespace-nowrap">
                  <div>{new Date(r.created_at).toLocaleString()}</div>
                  {r.ip_address && <div className="font-mono">{r.ip_address}</div>}
                </div>
              </li>
            ))}
          </ul>
        )}

        {data && data.total > data.page_size && (
          <div className="p-3 flex justify-between items-center border-t border-gray-100">
            <Button variant="ghost" size="sm" disabled={page === 1} onClick={() => setPage((p) => p - 1)}>
              ← Previous
            </Button>
            <span className="text-xs text-gray-500">
              Page {page} of {Math.ceil(data.total / data.page_size)}
            </span>
            <Button
              variant="ghost"
              size="sm"
              disabled={page >= Math.ceil(data.total / data.page_size)}
              onClick={() => setPage((p) => p + 1)}
            >
              Next →
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}
