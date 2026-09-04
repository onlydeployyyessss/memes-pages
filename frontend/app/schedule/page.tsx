"use client";

import { useEffect, useState } from "react";
import { ErrorNote, PageHead } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate, useApi } from "@/lib/hooks";

const FIELDS: [string, string, string][] = [
  ["batch_size", "Batch size", "Videos per batch"],
  ["initial_delay_minutes", "Initial delay (min)", "Wait before the first post of a batch"],
  ["min_delay_minutes", "Min gap between posts (min)", ""],
  ["max_delay_minutes", "Max gap between posts (min)", "Random gap within [min, max]"],
  ["fixed_delay_minutes", "Fixed gap (min)", "0 = variable random gap"],
  ["rest_period_minutes", "Rest between batches (min)", "e.g. 330 = 5.5 hours"],
  ["max_posts_per_day", "Max posts per day", ""],
  ["post_window_start", "Posting window start (hour)", "Local hour 0–23"],
  ["post_window_end", "Posting window end (hour)", ""],
  ["quiet_hours_start", "Quiet hours start (hour)", "Empty = disabled"],
  ["quiet_hours_end", "Quiet hours end (hour)", ""],
];

export default function SchedulePage() {
  const cfg = useApi<any>("/schedule/settings");
  const plan = useApi<any>("/schedule/plan?limit=25");
  const [form, setForm] = useState<any>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (cfg.data && form === null) setForm({ ...cfg.data });
  }, [cfg.data, form]);

  async function save() {
    const payload: any = {};
    for (const [key] of FIELDS) {
      const v = form[key];
      payload[key] = v === "" ? null : Number(v);
    }
    payload.timezone = form.timezone || "UTC";
    await api.put("/schedule/settings", payload);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
    cfg.reload();
    plan.reload();
  }

  async function recompute() {
    await api.post("/schedule/recompute");
    plan.reload();
  }

  return (
    <div>
      <PageHead
        title="📅 Batch Scheduler"
        desc="Spread publishing over time — batches, variable gaps, rest periods, quiet hours"
        actions={
          <>
            <button className="btn-primary" onClick={save}>{saved ? "✅ Saved" : "💾 Save"}</button>
            <button className="btn-ghost" onClick={recompute}>🔄 Recompute plan</button>
          </>
        }
      />
      {(cfg.error || plan.error) && <ErrorNote msg={cfg.error ?? plan.error ?? ""} />}

      <div className="grid lg:grid-cols-2 gap-4">
        <div className="panel p-4">
          <h3 className="text-sm text-gray-400 mb-4">⚙️ Scheduler settings</h3>
          {form && (
            <>
              <div className="grid sm:grid-cols-2 gap-3">
                {FIELDS.map(([key, label, hint]) => (
                  <div key={key}>
                    <label className="label">{label}</label>
                    <input
                      className="input" type="number" step="any"
                      value={form[key] ?? ""}
                      onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                    />
                    {hint && <p className="text-[10px] text-gray-600 mt-1">{hint}</p>}
                  </div>
                ))}
                <div>
                  <label className="label">Timezone</label>
                  <input className="input" value={form.timezone ?? "UTC"}
                    onChange={(e) => setForm({ ...form, timezone: e.target.value })} />
                </div>
              </div>
            </>
          )}
          <div className="mt-4 text-xs text-gray-500 bg-panel2 rounded-lg p-3">
            Example: batch 10 • initial delay 60 min • gap 1–5 min • rest 330 min
            → Video 1 → wait → Video 2 → … → 10 videos → 5.5 h rest → next batch.
          </div>
        </div>

        <div className="panel p-4">
          <h3 className="text-sm text-gray-400 mb-4">🗓 Planned posts</h3>
          <div className="space-y-1 max-h-[480px] overflow-y-auto">
            {(plan.data?.items ?? []).map((p: any) => (
              <div key={p.job_id} className="flex items-center gap-3 text-sm border-t border-line/60 py-2 first:border-0">
                <span className="text-xs text-gray-500 w-28">{fmtDate(p.publish_at)}</span>
                <span className="flex-1 truncate">{p.content_title}</span>
                <span className="badge">{p.account}</span>
                <span className="text-xs text-gray-600">batch #{p.batch_id ?? "—"}</span>
              </div>
            ))}
            {!plan.data?.items?.length && (
              <p className="text-sm text-gray-500">Nothing scheduled yet.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
