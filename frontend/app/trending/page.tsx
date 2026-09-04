"use client";

import { useState } from "react";
import { ErrorNote, PageHead, ScoreBar, StatusBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate, fmtInt, useApi } from "@/lib/hooks";

export default function TrendingPage() {
  const [minScore, setMinScore] = useState(0);
  const [status, setStatus] = useState("");
  const { data, error, reload } = useApi<any>(
    `/trending?limit=50&min_score=${minScore}${status ? `&status=${status}` : ""}`
  );
  const [open, setOpen] = useState<number | null>(null);

  async function disableSource(id: number) {
    if (!confirm("Disable this content's source?")) return;
    await api.post(`/trending/${id}/disable-source`);
    reload();
  }
  async function forceQueue(id: number) {
    const res = await api.post(`/trending/${id}/queue`);
    alert(`Pipeline result: ${res.status}`);
    reload();
  }

  return (
    <div>
      <PageHead
        title="🔥 Trending"
        desc="Trend Hunter candidates — scores 0–100, rules applied automatically"
        actions={
          <>
            <select className="input w-auto" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">All statuses</option>
              {["detected", "processing", "queued", "scheduled", "published", "failed", "skipped"].map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
            <select className="input w-auto" value={minScore} onChange={(e) => setMinScore(+e.target.value)}>
              <option value={0}>Any score</option>
              <option value={60}>≥ 60</option>
              <option value={85}>≥ 85 🔥</option>
              <option value={90}>≥ 90 🔥🔥</option>
            </select>
          </>
        }
      />
      {error && <ErrorNote msg={error} />}

      <div className="space-y-3">
        {(data?.items ?? []).map((t: any) => (
          <div key={t.id} className="panel p-4">
            <div className="flex flex-wrap items-center gap-3">
              <ScoreBar score={t.trend_score ?? 0} />
              <div className="flex-1 min-w-40">
                <div className="text-sm font-medium text-white truncate">{t.title || t.url}</div>
                <div className="text-xs text-gray-500 mt-0.5">
                  {t.source_name ?? "manual"} • {t.category} • age{" "}
                  {t.trend_signals?.content_age_hours != null
                    ? `${Number(t.trend_signals.content_age_hours).toFixed(0)}h`
                    : "—"}
                </div>
              </div>
              <StatusBadge status={t.status} />
              <div className="text-xs text-gray-500 hidden md:block">
                👁 {fmtInt(t.trend_signals?.views)} ❤️ {fmtInt(t.trend_signals?.likes)} 💬 {fmtInt(t.trend_signals?.comments)}
              </div>
              <button className="btn-ghost" onClick={() => setOpen(open === t.id ? null : t.id)}>
                {open === t.id ? "▲" : "▼"}
              </button>
            </div>

            {open === t.id && (
              <div className="border-t border-line mt-3 pt-3 text-sm space-y-2">
                <div className="text-gray-400">
                  Growth: +{Number(t.trend_signals?.growth_rate_percent_per_hour ?? 0).toFixed(0)}%/h •
                  Engagement rate: {(Number(t.trend_signals?.engagement_rate ?? 0) * 100).toFixed(1)}% •
                  Discovered {fmtDate(t.discovered_at)}
                </div>
                {t.rule_decision && (
                  <div className={`rounded-lg border px-3 py-2 text-xs ${t.rule_decision.approved ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300" : "border-amber-500/30 bg-amber-500/10 text-amber-300"}`}>
                    {t.rule_decision.approved
                      ? "✅ Approved automatically by the rule engine"
                      : `⛔️ Rule engine: ${t.rule_decision.reasons?.join("; ")}`}
                  </div>
                )}
                {t.url && (
                  <a href={t.url} target="_blank" rel="noreferrer" className="text-xs text-accent hover:underline break-all">
                    {t.url}
                  </a>
                )}
                <div className="flex gap-2 pt-1">
                  <button className="btn-danger" onClick={() => disableSource(t.id)}>🚫 Disable source</button>
                  <button className="btn-green" onClick={() => forceQueue(t.id)}>📥 Force queue</button>
                </div>
              </div>
            )}
          </div>
        ))}
        {!data?.items?.length && !error && (
          <div className="panel p-8 text-center text-gray-500 text-sm">
            No trending content yet. Add RSS feeds under <b>Sources</b>, enable automation,
            and Trend Hunter will start scoring incoming items.
          </div>
        )}
      </div>
    </div>
  );
}
