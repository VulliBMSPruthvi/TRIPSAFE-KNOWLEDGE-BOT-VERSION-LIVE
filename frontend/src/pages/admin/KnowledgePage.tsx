import { useEffect, useRef, useState } from "react";
import {
  api,
  type IndexBuildRow,
  type IndexStatus,
  type KnowledgeFileRow,
} from "@/api/client";
import { Card, CardHeader } from "@/components/Card";
import { Button } from "@/components/Button";
import { Badge } from "@/components/Badge";
import { Spinner } from "@/components/Spinner";

const statusTone = {
  pending: "warning",
  running: "info",
  complete: "success",
  failed: "danger",
} as const;

function formatElapsed(startedAtIso: string): string {
  const elapsed = Math.max(0, Math.floor((Date.now() - new Date(startedAtIso).getTime()) / 1000));
  const min = Math.floor(elapsed / 60);
  const sec = elapsed % 60;
  return min > 0 ? `${min}m ${sec}s` : `${sec}s`;
}

export function KnowledgePage() {
  const [files, setFiles] = useState<KnowledgeFileRow[]>([]);
  const [status, setStatus] = useState<IndexStatus | null>(null);
  const [builds, setBuilds] = useState<IndexBuildRow[]>([]);
  const [uploading, setUploading] = useState(false);
  const [building, setBuilding] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const refresh = async () => {
    const [f, s, b] = await Promise.all([
      api.listFiles(),
      api.indexStatus(),
      api.listBuilds(),
    ]);
    setFiles(f);
    setStatus(s);
    setBuilds(b);
  };

  useEffect(() => { void refresh(); }, []);

  // Poll while a build is in flight
  useEffect(() => {
    const inFlight = builds[0]?.status === "pending" || builds[0]?.status === "running";
    if (!inFlight) return;
    const t = setInterval(() => void refresh(), 3000);
    return () => clearInterval(t);
  }, [builds]);

  const onUpload = async (file: File) => {
    setErr(null);
    setUploading(true);
    try {
      await api.uploadFile(file);
      await refresh();
    } catch (e) {
      setErr(String(e));
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const onDelete = async (id: string) => {
    if (!confirm("Delete this file? You'll need to rebuild the index for it to take effect.")) return;
    try {
      await api.deleteFile(id);
      await refresh();
    } catch (e) {
      setErr(String(e));
    }
  };

  const onRebuild = async () => {
    setErr(null);
    setBuilding(true);
    try {
      await api.rebuildIndex();
      await refresh();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBuilding(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-gray-900">Knowledge Base</h1>
        <p className="text-sm text-gray-500 mt-1">
          Manage source documents and rebuild the search index.
        </p>
      </div>

      {err && <Card className="border-danger/30"><p className="text-danger text-sm">{err}</p></Card>}

      <Card>
        <CardHeader
          title="Live index"
          description="Snapshot of what the chatbot is searching against right now."
        />
        {status === null ? (
          <Spinner />
        ) : (
          <div className="flex flex-wrap items-center gap-4">
            <Badge tone={status.loaded ? "success" : "warning"}>
              {status.loaded ? "Loaded" : "Not built"}
            </Badge>
            <span className="text-sm text-gray-700">{status.chunk_count} chunks</span>
            {status.loaded_at && (
              <span className="text-xs text-gray-400">
                loaded {new Date(status.loaded_at).toLocaleString()}
              </span>
            )}
            <div className="ml-auto">
              <Button
                onClick={() => void onRebuild()}
                loading={building || builds[0]?.status === "running" || builds[0]?.status === "pending"}
              >
                Rebuild index
              </Button>
            </div>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader
          title="Source files"
          description="Upload .docx or .csv. Up to 20 MB each."
          action={
            <>
              <input
                ref={inputRef}
                type="file"
                accept=".docx,.csv"
                className="hidden"
                onChange={(e) => e.target.files && e.target.files[0] && onUpload(e.target.files[0])}
              />
              <Button
                onClick={() => inputRef.current?.click()}
                loading={uploading}
              >
                Upload file
              </Button>
            </>
          }
        />
        {files.length === 0 ? (
          <p className="text-sm text-gray-500">No files uploaded yet.</p>
        ) : (
          <ul className="divide-y divide-gray-100">
            {files.map((f) => (
              <li key={f.id} className="py-3 flex items-center gap-3">
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-900 truncate">{f.filename}</div>
                  <div className="text-xs text-gray-500">
                    {(f.file_size / 1024).toFixed(1)} KB •{" "}
                    {new Date(f.uploaded_at).toLocaleString()}
                  </div>
                </div>
                <Button size="sm" variant="ghost" onClick={() => void onDelete(f.id)}>
                  Delete
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card>
        <CardHeader title="Build history" description="Last 20 rebuild attempts." />
        {builds.length === 0 ? (
          <p className="text-sm text-gray-500">No builds yet.</p>
        ) : (
          <ul className="divide-y divide-gray-100">
            {builds.map((b) => (
              <li key={b.id} className="py-3 flex items-center gap-3">
                <Badge tone={statusTone[b.status]}>{b.status}</Badge>
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-gray-700">
                    {b.chunk_count ?? "—"} chunks
                    {b.source_files && b.source_files.length > 0 && (
                      <span className="text-gray-400"> · {b.source_files.length} files</span>
                    )}
                    {(b.status === "pending" || b.status === "running") && (
                      <span className="text-info ml-2">· elapsed {formatElapsed(b.started_at)}</span>
                    )}
                  </div>
                  {b.error_message && (
                    <div className="text-xs text-danger mt-1">{b.error_message}</div>
                  )}
                </div>
                <span className="text-xs text-gray-400">
                  {new Date(b.started_at).toLocaleString()}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
