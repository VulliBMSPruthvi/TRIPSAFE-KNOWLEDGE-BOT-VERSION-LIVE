import { useEffect, useState } from "react";
import { api, type AdminUserRow, type UserRole } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { Card } from "@/components/Card";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Spinner } from "@/components/Spinner";

export function UsersPage() {
  const { user: me } = useAuth();
  const [rows, setRows] = useState<AdminUserRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      setRows(await api.listUsers());
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const toggleRole = async (u: AdminUserRow) => {
    setBusy(u.id);
    const next: UserRole = u.role === "admin" ? "user" : "admin";
    try {
      const updated = await api.changeRole(u.id, next);
      setRows((rs) => rs.map((r) => (r.id === u.id ? updated : r)));
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(null);
    }
  };

  const toggleActive = async (u: AdminUserRow) => {
    setBusy(u.id);
    try {
      const updated = await api.changeActive(u.id, !u.is_active);
      setRows((rs) => rs.map((r) => (r.id === u.id ? updated : r)));
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-gray-900">Users</h1>
        <p className="text-sm text-gray-500 mt-1">Manage roles and account access.</p>
      </div>

      {err && <Card className="border-danger/30"><p className="text-danger text-sm">{err}</p></Card>}

      <Card padded={false} className="overflow-hidden">
        {loading ? (
          <div className="p-10 flex justify-center"><Spinner /></div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 text-gray-500 text-xs uppercase tracking-wider">
                <tr>
                  <th className="text-left px-4 py-3">User</th>
                  <th className="text-left px-4 py-3">Role</th>
                  <th className="text-left px-4 py-3">Status</th>
                  <th className="text-left px-4 py-3">Last login</th>
                  <th className="text-right px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {rows.map((u) => {
                  const isSelf = me?.id === u.id;
                  return (
                    <tr key={u.id}>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          {u.avatar_url ? (
                            <img src={u.avatar_url} alt="" referrerPolicy="no-referrer" className="h-8 w-8 rounded-full" />
                          ) : (
                            <div className="h-8 w-8 rounded-full bg-gray-200 flex items-center justify-center text-xs font-medium">
                              {u.name.slice(0, 1).toUpperCase()}
                            </div>
                          )}
                          <div>
                            <div className="font-medium text-gray-900">{u.name}</div>
                            <div className="text-xs text-gray-500">{u.email}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <Badge tone={u.role === "admin" ? "brand" : "neutral"}>{u.role}</Badge>
                      </td>
                      <td className="px-4 py-3">
                        <Badge tone={u.is_active ? "success" : "danger"}>
                          {u.is_active ? "active" : "deactivated"}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-gray-500 text-xs">
                        {u.last_login ? new Date(u.last_login).toLocaleString() : "—"}
                      </td>
                      <td className="px-4 py-3 text-right space-x-2 whitespace-nowrap">
                        <Button
                          size="sm"
                          variant="secondary"
                          disabled={isSelf || busy === u.id}
                          onClick={() => void toggleRole(u)}
                          title={isSelf ? "You cannot change your own role" : undefined}
                        >
                          {u.role === "admin" ? "Demote" : "Promote"}
                        </Button>
                        <Button
                          size="sm"
                          variant={u.is_active ? "danger" : "primary"}
                          disabled={isSelf || busy === u.id}
                          onClick={() => void toggleActive(u)}
                          title={isSelf ? "You cannot deactivate yourself" : undefined}
                        >
                          {u.is_active ? "Deactivate" : "Reactivate"}
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
