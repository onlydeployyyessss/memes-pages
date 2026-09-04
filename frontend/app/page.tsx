"use client";

import { useState } from "react";
import { ErrorNote, Kpi, PageHead } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate, fmtInt, useApi } from "@/lib/hooks";

import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

export default function OverviewPage() {
  const ov = useApi<any>("/analytics/overview");
  const auto = useApi<any>("/automation/status");
  const ts = useApi<any>("/analytics/timeseries?days=14");
  const trend = useApi<any>("/trending?limit=5");
  const [busy, setBusy] = useState(false);

  async function automation(action: string) {
    setBusy(true);
    try {
      await api.post(`/automation/${action}`);
      auto.reload();
    } finally {
      setBusy(false);
    }
  }

  const d = ov.data;
  const state = auto.data;
  const series = (ts.data?.series ?? []).map((r: any) => ({
    ...r, er: r.views ? Number((((r.likes + r.comments + r.shares) / r.views) * 100).toFixed(2)) : 0,
  }));

  return (
    <div>
      <PageHead
        title="📊 Overview"
        desc="Network-wide automation status and performance"
        actions={
          state && (
            <>
              <span className="badge mr-2">{state.label}</span>
              {!state.enabled ? (
                <button className="btn-green" disabled={busy} onClick={() => automation("start")}>▶ Start</button>
              ) : state.paused ? (
                <button className="btn-green" disabled={busy} onClick={() => automation("resume")}>▶ Resume</button>
              ) : (
                <button className="btn-ghost" disabled={busy} onClick={() => automation("pause")}>⏸ Pause</button>
              )}
              <button className="btn-primary" disabled={busy} onClick={() => automation("run-now")}>🔄 Run Now</button>
              <button className="btn-danger" disabled={busy} onClick={() => automation("stop")}>⏹ Stop</button>
            </>
          )
        }
      />
      {ov.error && <ErrorNote msg={ov.error} />}

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        <Kpi icon="📱" label="Accounts" value={d ? `${d.active_accounts}/${d.total_accounts}` : "—"} sub="active / total" />
        <Kpi icon="🎬" label="Detected" value={d ? fmtInt(d.videos_detected) : "—"} />
        <Kpi icon="📥" label="Queued" value={d ? fmtInt(d.videos_queued) : "—"} />
        <Kpi icon="🟢" label="Published" value={d ? fmtInt(d.videos_published) : "—"} />
        <Kpi icon="👁" label="Views (7d)" value={d ? fmtInt(d.total_views) : "—"} />
        <Kpi icon="👥" label="Followers" value={d ? fmtInt(d.total_followers) : "—"} sub={d ? `+${fmtInt(d.new_followers_7d)} in 7d` : ""} />
      </div>

      <div className="grid lg:grid-cols-3 gap-4 mt-4">
        <div className="panel p-4 lg:col-span-2">
          <h3 className="text-sm text-gray-400 mb-3">👁 Views per day (14 days)</h3>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={series}>
                <defs>
                  <linearGradient id="vg" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#6366f1" stopOpacity={0.5} />
                    <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#1f2937" strokeDasharray="3 3" />
                <XAxis dataKey="date" tick={{ fill: "#6b7280", fontSize: 11 }} tickFormatter={(v: string) => v.slice(5)} />
                <YAxis tick={{ fill: "#6b7280", fontSize: 11 }} tickFormatter={(v: number) => fmtInt(v)} />
                <Tooltip contentStyle={{ background: "#111827", border: "1px solid #1f2937", borderRadius: 8 }} />
                <Area type="monotone" dataKey="views" stroke="#6366f1" fill="url(#vg)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel p-4">
          <h3 className="text-sm text-gray-400 mb-3">🤖 Automation</h3>
          {state && (
            <div className="space-y-2 text-sm">
              <Row k="State" v={state.label} />
              <Row k="Last run" v={`${state.last_run_ago} (${state.last_run_job || "—"})`} />
              <Row k="Next post" v={state.next_run ? fmtDate(state.next_run) : "—"} />
              <Row k="Queue" v={String(state.queue_size + state.scheduled_count)} />
              <Row k="Active jobs" v={String(state.active_jobs)} />
              <Row k="Failed jobs" v={String(state.failed_jobs)} />
              <Row k="Engagement (7d)" v={`${d?.engagement_rate ?? 0}% (${(d?.engagement_delta ?? 0) >= 0 ? "+" : ""}${d?.engagement_delta ?? 0})`} />
              <Row k="Growth (7d)" v={`${d?.growth_rate ?? 0}%`} />
            </div>
          )}
        </div>
      </div>

      <div className="panel p-4 mt-4">
        <h3 className="text-sm text-gray-400 mb-3">🔥 Top trending right now</h3>
        <div className="space-y-2">
          {(trend.data?.items ?? []).map((t: any) => (
            <div key={t.id} className="flex items-center gap-3 text-sm border-t border-line/60 py-2 first:border-0">
              <span className={`font-semibold ${t.trend_score >= 85 ? "text-emerald-300" : "text-gray-300"}`}>
                {t.trend_score?.toFixed(0)}
              </span>
              <span className="flex-1 truncate">{t.title || t.url}</span>
              <span className="badge hidden sm:inline-flex">{t.category}</span>
              <span className="text-xs text-gray-500">{t.status}</span>
            </div>
          ))}
          {!trend.data?.items?.length && !trend.loading && (
            <p className="text-sm text-gray-500">Nothing scored yet — add sources and run discovery.</p>
          )}
        </div>
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between border-t border-line/60 py-1.5 first:border-0">
      <span className="text-gray-500">{k}</span>
      <span className="text-gray-200 text-right">{v}</span>
    </div>
  );
}
