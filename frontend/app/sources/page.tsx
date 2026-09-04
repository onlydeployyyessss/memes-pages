"use client";

import { useState } from "react";
import { ErrorNote, PageHead, StatusBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate, useApi } from "@/lib/hooks";

export default function SourcesPage() {
  const { data, error, reload } = useApi<any>("/sources");
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState<any>({
    name: "", source_type: "rss", url: "", authorization: "authorized",
    categories: "memes", priority: 5, check_interval_minutes: 15,
  });
  const [checking, setChecking] = useState<number | null>(null);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    await api.post("/sources", {
      ...form,
      categories: form.categories.split(",").map((x: string) => x.trim()).filter(Boolean),
    });
    setAdding(false);
    reload();
  }

  async function setAuth(src: any, authorization: string) {
    await api.post(`/sources/${src.id}/authorize`, { authorization });
    reload();
  }
  async function toggleEnabled(src: any) {
    await api.patch(`/sources/${src.id}`, { enabled: !src.enabled });
    reload();
  }
  async function checkNow(id: number) {
    setChecking(id);
    try {
      const res = await api.post(`/sources/${id}/check`);
      alert(`Discovered ${res.created} new item(s) (${res.skipped} skipped)`);
    } catch (e: any) {
      alert(`Check failed: ${e.message}`);
    } finally {
      setChecking(null);
      reload();
    }
  }

  return (
    <div>
      <PageHead
        title="📡 Sources"
        desc="Discovery sources & the authorization system — automation only processes 'Authorized' sources"
        actions={<button className="btn-primary" onClick={() => setAdding(!adding)}>+ Add source</button>}
      />
      {error && <ErrorNote msg={error} />}

      {adding && (
        <form onSubmit={create} className="panel p-4 mb-4 grid md:grid-cols-3 gap-3 items-end">
          <div className="md:col-span-2">
            <label className="label">Source name</label>
            <input className="input" required placeholder="🔥 Viral Memes" value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <label className="label">Type</label>
            <select className="input" value={form.source_type}
              onChange={(e) => setForm({ ...form, source_type: e.target.value })}>
              <option value="rss">RSS feed</option>
              <option value="authorized_feed">Authorized JSON feed</option>
              <option value="agent_reach">Agent-Reach (experimental)</option>
            </select>
          </div>
          <div className="md:col-span-2">
            <label className="label">URL</label>
            <input className="input" required placeholder="https://example.com/feed.xml" value={form.url}
              onChange={(e) => setForm({ ...form, url: e.target.value })} />
          </div>
          <div>
            <label className="label">Authorization</label>
            <select className="input" value={form.authorization}
              onChange={(e) => setForm({ ...form, authorization: e.target.value })}>
              <option value="authorized">Authorized ✅</option>
              <option value="not_authorized">Not authorized</option>
              <option value="disabled">Disabled</option>
            </select>
          </div>
          <div>
            <label className="label">Categories (comma sep)</label>
            <input className="input" value={form.categories}
              onChange={(e) => setForm({ ...form, categories: e.target.value })} />
          </div>
          <div>
            <label className="label">Check interval (min)</label>
            <input className="input" type="number" min={5} value={form.check_interval_minutes}
              onChange={(e) => setForm({ ...form, check_interval_minutes: +e.target.value })} />
          </div>
          <button className="btn-primary justify-center">Add source</button>
        </form>
      )}

      <div className="panel overflow-x-auto">
        <table className="w-full min-w-[720px]">
          <thead>
            <tr>
              <th className="th">Source</th>
              <th className="th">Type</th>
              <th className="th">Authorization</th>
              <th className="th">Interval</th>
              <th className="th">Last check</th>
              <th className="th text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {(data?.items ?? []).map((src: any) => (
              <tr key={src.id}>
                <td className="td">
                  <div className="font-medium text-white">{src.name}</div>
                  <div className="text-xs text-gray-500 truncate max-w-72">{src.url || "—"}</div>
                  <div className="text-xs text-gray-600">{(src.categories ?? []).join(", ")}</div>
                </td>
                <td className="td"><span className="badge">{src.source_type}</span></td>
                <td className="td">
                  <select className="input w-auto text-xs py-1" value={src.authorization}
                    onChange={(e) => setAuth(src, e.target.value)}>
                    <option value="authorized">✅ authorized</option>
                    <option value="not_authorized">⛔️ not authorized</option>
                    <option value="disabled">⚫ disabled</option>
                  </select>
                </td>
                <td className="td text-xs">{src.check_interval_minutes} min</td>
                <td className="td text-xs">{fmtDate(src.last_checked_at)}</td>
                <td className="td">
                  <div className="flex justify-end gap-2">
                    <button className="btn-ghost" onClick={() => toggleEnabled(src)}>
                      {src.enabled ? "⏸ Disable" : "▶ Enable"}
                    </button>
                    <button className="btn-ghost" disabled={checking === src.id}
                      onClick={() => checkNow(src.id)}>
                      {checking === src.id ? "…" : "🔄 Check now"}
                    </button>
                    <button className="btn-danger"
                      onClick={async () => { if (confirm(`Delete ${src.name}?`)) { await api.del(`/sources/${src.id}`); reload(); } }}>
                      🗑
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {!data?.items?.length && (
              <tr><td className="td text-center text-gray-500" colSpan={6}>No sources yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-gray-600 mt-3">
        🔐 Authorization matters: automatic discovery → trend scoring → publishing runs
        <b> only for sources marked “authorized”</b>. “Not authorized” sources are scored but
        never auto-processed.
      </p>
    </div>
  );
}
