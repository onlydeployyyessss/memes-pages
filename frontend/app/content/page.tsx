"use client";

import { useEffect, useRef, useState } from "react";
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
  const [filesCount, setFilesCount] = useState(0);
  const [igProfile, setIgProfile] = useState("");
  const [igLimit, setIgLimit] = useState(10);
  const [igMsg, setIgMsg] = useState<string | null>(null);
  const [igUser, setIgUser] = useState("");
  const [igPass, setIgPass] = useState("");
  const [igSessions, setIgSessions] = useState<string[]>([]);

  async function loadIgStatus() {
    try {
      const st = await api.get("/instaloader/status");
      setIgSessions(st.sessions ?? []);
    } catch { /* ignore */ }
  }
  useEffect(() => { loadIgStatus(); }, []);

  async function igLogin(e: React.FormEvent) {
    e.preventDefault();
    setIgMsg("⏳ logging in…");
    try {
      await api.post("/instaloader/login", { username: igUser, password: igPass });
      setIgMsg("🟢 session saved (password not stored)");
      setIgPass("");
      loadIgStatus();
    } catch (err: any) {
      setIgMsg(`🔴 ${err.message}`);
    }
  }

  async function igFetch(e: React.FormEvent) {
    e.preventDefault();
    if (!igProfile.trim()) return;
    setIgMsg("⏳ starting import…");
    try {
      await api.post("/instaloader/fetch", { profile: igProfile.trim(), limit: igLimit });
      const poll = setInterval(async () => {
        try {
          const st = await api.get("/instaloader/status");
          const j = st.job;
          setIgMsg(
            j.running
              ? `⏳ @${j.profile}: fetched ${j.fetched}, queued ${j.queued}, failed ${j.failed}…`
              : `✅ done — fetched ${j.fetched}, queued ${j.queued}, failed ${j.failed}` +
                (j.messages?.length ? ` — ${j.messages.filter((m: string) => m.startsWith(("🔴"))).slice(0, 2).join(" · ")}` : "")
          );
          if (!j.running) { clearInterval(poll); reload(); loadIgStatus(); }
        } catch { clearInterval(poll); }
      }, 4000);
    } catch (err: any) {
      setIgMsg(`🔴 ${err.message}`);
    }
  }
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);

  async function upload(e: React.FormEvent) {
    e.preventDefault();
    const files = Array.from(fileRef.current?.files ?? []);
    if (!files.length) return;
    setUploading(true);
    setUploadMsg(null);
    const results: string[] = [];
    try {
      for (let i = 0; i < files.length; i++) {
        const f = files[i];
        setUploadMsg(`⏳ Uploading ${i + 1}/${files.length}: ${f.name}…`);
        try {
          const form = new FormData();
          form.append("file", f);
          const res = await api.upload("/content/upload", form);
          const icon = res.status === "queued" ? "🟢" : res.status === "skipped" ? "⚪" : "🔴";
          results.push(`${icon} ${f.name}: ${res.status}${res.error ? ` — ${res.error}` : ""}`);
        } catch (err: any) {
          results.push(`🔴 ${f.name}: ${err.message}`);
        }
      }
      setUploadMsg(results.join("  ·  "));
      reload();
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

      <div className="panel p-4 mb-4">
        <div className="font-semibold mb-2">📥 Import reels from an Instagram profile</div>
        <form onSubmit={igFetch} className="flex flex-wrap items-center gap-2">
          <input className="input w-auto" placeholder="username (e.g. lgh.stsh)" value={igProfile} onChange={(e) => setIgProfile(e.target.value)} />
          <label className="text-sm text-gray-400">count:</label>
          <input type="number" min={1} max={30} className="input w-24" value={igLimit} onChange={(e) => setIgLimit(Number(e.target.value) || 10)} />
          <button className="btn-primary" disabled={uploading}>📥 Import reels</button>
          <button type="button" className="btn-ghost" onClick={async () => {
            try { await api.post("/instaloader/cancel", {}); setIgMsg("🛑 cancel requested…"); } catch (e: any) { setIgMsg(`🔴 ${e.message}`); }
          }}>🛑 Cancel</button>
          {igMsg && <span className="text-sm text-gray-400 w-full">{igMsg}</span>}
          <p className="text-xs text-gray-500 w-full">With a burner login: ~3–5 min for 10 reels. Without login Instagram slow-lanes server downloads (can hang) — the job auto-stops after 15 min.</p>
        </form>
        <details className="mt-2 text-sm text-gray-400">
          <summary className="cursor-pointer">Optional: IG login (raises limits — use a burner account, not your posting account)</summary>
          <form onSubmit={igLogin} className="flex flex-wrap items-center gap-2 mt-2">
            <input className="input w-auto" placeholder="instagram username" value={igUser} onChange={(e) => setIgUser(e.target.value)} />
            <input className="input w-auto" type="password" placeholder="password" value={igPass} onChange={(e) => setIgPass(e.target.value)} />
            <button className="btn-ghost">🔐 Save session</button>
            {igSessions.length > 0 && <span>active sessions: {igSessions.join(", ")}</span>}
          </form>
          <p className="mt-1 text-xs">Password is used once and never stored. Only import content you own or have permission to re-post.</p>
        </details>
      </div>

      <form onSubmit={upload} className="panel p-4 mb-4 flex flex-wrap items-center gap-3">
        <input ref={fileRef} type="file" accept="video/*" multiple onChange={(e) => setFilesCount(e.target.files?.length ?? 0)} className="text-sm text-gray-400 file:mr-3 file:btn-ghost" />
        <button className="btn-primary" disabled={uploading}>
          {uploading ? "Processing…" : filesCount > 1 ? `⬆️ Upload ${filesCount} videos` : "⬆️ Upload video"}
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
