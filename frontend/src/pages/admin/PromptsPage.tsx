import { useEffect, useState } from "react";
import { api, type SystemPromptRow } from "@/api/client";
import { Card, CardHeader } from "@/components/Card";
import { Button } from "@/components/Button";
import { Textarea } from "@/components/Input";
import { Badge } from "@/components/Badge";

const DEFAULT_PROMPT =
  "You are a knowledgeable TripSafe travel insurance assistant. Answer accurately based on the provided context. Be professional and helpful.";

export function PromptsPage() {
  const [active, setActive] = useState<SystemPromptRow | null>(null);
  const [history, setHistory] = useState<SystemPromptRow[]>([]);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const refresh = async () => {
    const [a, h] = await Promise.all([api.activePrompt(), api.promptHistory()]);
    setActive(a);
    setHistory(h);
    setDraft(a?.content ?? DEFAULT_PROMPT);
  };

  useEffect(() => { void refresh(); }, []);

  const save = async () => {
    if (draft.length < 10) {
      setErr("Prompt must be at least 10 characters.");
      return;
    }
    setSaving(true);
    setErr(null);
    try {
      await api.savePrompt(draft);
      await refresh();
    } catch (e) {
      setErr(String(e));
    } finally {
      setSaving(false);
    }
  };

  const revert = async (id: string) => {
    if (!confirm("Activate this older version?")) return;
    try {
      await api.activatePrompt(id);
      await refresh();
    } catch (e) {
      setErr(String(e));
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-gray-900">System Prompt</h1>
        <p className="text-sm text-gray-500 mt-1">
          The bot's persona and instructions. Changes take effect on the very next chat — no restart needed.
        </p>
      </div>

      {err && <Card className="border-danger/30"><p className="text-danger text-sm">{err}</p></Card>}

      <Card>
        <CardHeader
          title="Current prompt"
          description={
            active
              ? `Updated ${new Date(active.created_at).toLocaleString()}`
              : "No saved prompt yet — using a default."
          }
          action={
            <Button onClick={() => void save()} loading={saving} disabled={draft.trim() === (active?.content ?? "")}>
              Save new version
            </Button>
          }
        />
        <Textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={8}
          hint={`${draft.length} characters`}
        />
      </Card>

      <Card>
        <CardHeader title="History" description="Last 10 versions. Revert to any of them." />
        {history.length === 0 ? (
          <p className="text-sm text-gray-500">No history yet — save a version to start tracking.</p>
        ) : (
          <ul className="divide-y divide-gray-100">
            {history.map((p) => (
              <li key={p.id} className="py-3 flex items-start gap-3">
                {p.is_active && <Badge tone="brand">Active</Badge>}
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-700 line-clamp-3">{p.content}</p>
                  <p className="text-xs text-gray-400 mt-1">{new Date(p.created_at).toLocaleString()}</p>
                </div>
                {!p.is_active && (
                  <Button size="sm" variant="ghost" onClick={() => void revert(p.id)}>
                    Revert
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
