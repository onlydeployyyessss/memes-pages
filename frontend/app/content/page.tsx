"use client";

import { useRef, useState } from "react";
import { ErrorNote, PageHead, StatusBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate, useApi } from "@/lib/hooks";

const STATUSES = ["detected", "processing", "queued", "scheduled", "published", "failed", "skipped"];

export default function ContentPage() {
  const [status, setStatus] = useState("");
  const { data, error, reload } = useApi<any>(
    `/content?limit=60${status ? `&status=${status}` : ""}`
  );
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);

  async function upload(e: React.FormEvent) {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadMsg(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await api.upload("/content/upload", form);
      setUploadMsg(`${res.status === "queued" ? "🟢" : res.status === "skipped" ? "⚪" : "🔴"} Upload processed: ${res.status}${res.error ? ` — ${res.error}` : ""}`);
      reload();
    } catch (err: any) {
      setUploadMsg(`🔴 ${err.message}`);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div>
      <PageHead
        title="🎬 Content Library"
        desc="Every discovered, uploaded, queued and published video"
        actions={
          <select className="input w-auto" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All statuses</option>
            {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        }
      />
      {error && <ErrorNote msg={error} />}

      <form onSubmit={upload} className="panel p-4 mb-4 flex flex-wrap items-center gap-3">
        <input ref={fileRef} type="file" accept="video/*" className="text-sm text-gray-400 file:mr-3 file:btn-ghost" />
        <button className="btn-primary" disabled={uploading}>
          {uploading ? "Processing…" : "⬆️ Upload video"}
        </button>
        {uploadMsg && <span className="text-sm text-gray-400">{uploadMsg}</span>}
      </form>

      <div className="panel overflow-x-auto">
        <table className="w-full min-w-[760px]">
          <thead>
            <tr>
              <th className="th">Content</th>
              <th className="th">Category</th>
              <th className="th">Score</th>
              <th className="th">Status</th>
              <th className="th">Discovered</th>
              <th className="th text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {(data?.items ?? []).map((c: any) => (
              <tr key={c.id}>
                <td className="td max-w-80">
                  <div className="truncate text-white">{c.title || c.url}</div>
                  {c.error && <div className="text-xs text-red-400 truncate">⚠️ {c.error}</div>}
                </td>
                <td className="td"><span className="badge">{c.category}</span></td>
                <td className="td">{c.trend_score != null ? c.trend_score.toFixed(0) : "—"}</td>
                <td className="td"><StatusBadge status={c.status} /></td>
                <td className="td text-xs">{fmtDate(c.discovered_at)}</td>
                <td className="td">
                  <div className="flex justify-end gap-2">
                    <button className="btn-ghost" onClick={async () => { await api.post(`/content/${c.id}/reprocess`); reload(); }}>
                      🔄
                    </button>
                    <button className="btn-danger"
                      onClick={async () => { if (confirm("Delete this content?")) { await api.del(`/content/${c.id}`); reload(); } }}>
                      🗑
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {!data?.items?.length && (
              <tr><td className="td text-center text-gray-500" colSpan={6}>No content yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
