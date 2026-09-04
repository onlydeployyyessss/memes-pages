"use client";

import { useState } from "react";
import { ErrorNote, PageHead, StatusBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate, useApi } from "@/lib/hooks";

export default function QueuePage() {
  const [status, setStatus] = useState("");
  const { data, error, reload } = useApi<any>(
    `/queue?limit=100${status ? `&status=${status}` : ""}`
  );

  async function act(job: any, action: string) {
    await api.post(`/queue/${job.id}/${action}`);
    reload();
  }
  async function publishNow(jobs: any[]) {
    await api.post("/queue/publish-now", { job_ids: jobs.map((j) => j.id) });
    reload();
  }

  return (
    <div>
      <PageHead
        title="📥 Publishing Queue"
        desc="Jobs across all destination accounts — batch-scheduled, never simultaneous"
        actions={
          <>
            <select className="input w-auto" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">All</option>
              {["queued", "scheduled", "publishing", "published", "failed", "cancelled"].map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
            <button className="btn-ghost" onClick={async () => { await api.post("/queue/reschedule"); reload(); }}>
              🗓 Reschedule
            </button>
          </>
        }
      />
      {error && <ErrorNote msg={error} />}

      <div className="panel overflow-x-auto">
        <table className="w-full min-w-[820px]">
          <thead>
            <tr>
              <th className="th">Job</th>
              <th className="th">Account</th>
              <th className="th">Publish at</th>
              <th className="th">Batch</th>
              <th className="th">Status</th>
              <th className="th text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {(data?.items ?? []).map((j: any) => (
              <tr key={j.id}>
                <td className="td max-w-72">
                  <div className="truncate">{j.content_title}</div>
                  {j.last_error && <div className="text-xs text-red-400 truncate">⚠️ {j.last_error}</div>}
                </td>
                <td className="td">@{j.account_username || j.account_name}</td>
                <td className="td text-xs">
                  {j.publish_at ? fmtDate(j.publish_at) : "awaiting schedule"}
                  {j.attempts > 0 && <span className="text-amber-400"> · attempt {j.attempts}</span>}
                </td>
                <td className="td text-xs">{j.batch_id ?? "—"}</td>
                <td className="td"><StatusBadge status={j.status} /></td>
                <td className="td">
                  <div className="flex justify-end gap-2">
                    {["failed", "cancelled"].includes(j.status) && (
                      <button className="btn-ghost" onClick={() => act(j, "retry")}>🔁 Retry</button>
                    )}
                    {["queued", "scheduled"].includes(j.status) && (
                      <>
                        <button className="btn-green" onClick={() => publishNow([j])}>🚀 Now</button>
                        <button className="btn-ghost" onClick={() => act(j, "cancel")}>✖</button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {!data?.items?.length && (
              <tr><td className="td text-center text-gray-500" colSpan={6}>Queue is empty.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
