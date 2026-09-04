"use client";

import { useEffect, useState } from "react";
import { ErrorNote, PageHead } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";

export default function SettingsPage() {
  const data = useApi<any>("/settings");
  const [form, setForm] = useState<any>(null);
  const [weightsText, setWeightsText] = useState("");
  const [savedMsg, setSavedMsg] = useState("");

  useEffect(() => {
    if (data.data && form === null) {
      setForm(JSON.parse(JSON.stringify(data.data)));
      setWeightsText(JSON.stringify(data.data.trend.weights, null, 2));
    }
  }, [data.data, form]);

  async function save() {
    setSavedMsg("");
    try {
      const weights = JSON.parse(weightsText);
      await api.put("/settings/rules", form.rules);
      await api.put("/settings/scheduler", form.scheduler);
      await api.put("/settings/publishing", form.publishing);
      await api.put("/settings/notifications", form.notifications);
      await api.put("/settings/discovery", form.discovery);
      await api.put("/settings/trend", { ...form.trend, weights });
      setSavedMsg("✅ Settings saved");
      data.reload();
    } catch (e: any) {
      setSavedMsg(`⚠️ ${e.message}`);
    }
  }

  if (data.error) return <ErrorNote msg={data.error} />;
  if (!form) return <p className="text-gray-500 text-sm">Loading settings…</p>;

  const num = (section: string, key: string, label: string, hint = "") => (
    <div>
      <label className="label">{label}</label>
      <input
        className="input" type="number" step="any"
        value={form[section][key] ?? ""}
        onChange={(e) => {
          const v = e.target.value;
          setForm({ ...form, [section]: { ...form[section], [key]: v === "" ? null : Number(v) } });
        }}
      />
      {hint && <p className="text-[10px] text-gray-600 mt-1">{hint}</p>}
    </div>
  );

  const csv = (section: string, key: string, label: string) => (
    <div>
      <label className="label">{label}</label>
      <input
        className="input"
        value={(form[section][key] ?? []).join(", ")}
        onChange={(e) =>
          setForm({
            ...form,
            [section]: {
              ...form[section],
              [key]: e.target.value.split(",").map((x) => x.trim()).filter(Boolean),
            },
          })
        }
      />
    </div>
  );

  return (
    <div>
      <PageHead
        title="⚙️ Settings"
        desc="Rule engine, trend weights, publishing safety and notifications"
        actions={
          <>
            {savedMsg && <span className="text-sm text-gray-400">{savedMsg}</span>}
            <button className="btn-primary" onClick={save}>💾 Save all</button>
          </>
        }
      />

      <div className="grid lg:grid-cols-2 gap-4">
        <div className="panel p-4">
          <h3 className="text-sm text-gray-400 mb-4">📋 Automatic rule engine</h3>
          <div className="grid sm:grid-cols-2 gap-3">
            {num("rules", "min_trend_score", "Min trend score (0–100)", "e.g. 85")}
            {num("rules", "min_engagement", "Min engagement", "likes+comments+shares")}
            {num("rules", "max_age_hours", "Max content age (hours)", "e.g. 24")}
            {num("rules", "max_videos_per_day", "Max videos per day")}
          </div>
          <div className="grid sm:grid-cols-2 gap-3 mt-3">
            {csv("rules", "allowed_categories", "Allowed categories (empty = all)")}
            {csv("rules", "allowed_keywords", "Allowed keywords")}
            {csv("rules", "blocked_keywords", "Blocked keywords")}
          </div>
          <label className="flex items-center gap-2 mt-4 text-sm text-gray-300">
            <input
              type="checkbox" checked={!!form.rules.require_authorized_source}
              onChange={(e) => setForm({ ...form, rules: { ...form.rules, require_authorized_source: e.target.checked } })}
            />
            Require authorized source (recommended — keep ON)
          </label>
          <label className="flex items-center gap-2 mt-2 text-sm text-gray-300">
            <input
              type="checkbox" checked={!!form.rules.require_video_media}
              onChange={(e) => setForm({ ...form, rules: { ...form.rules, require_video_media: e.target.checked } })}
            />
            Only accept video media
          </label>
        </div>

        <div className="panel p-4">
          <h3 className="text-sm text-gray-400 mb-4">🔥 Trend Hunter weights</h3>
          <p className="text-xs text-gray-500 mb-2">
            Weights for views / likes / comments / shares / engagement_rate /
            growth_rate / velocity / freshness / source_history (should sum ≈ 1.0).
          </p>
          <textarea
            className="input h-44 font-mono text-xs"
            value={weightsText}
            onChange={(e) => setWeightsText(e.target.value)}
          />
          <div className="grid sm:grid-cols-2 gap-3 mt-3">
            {num("trend", "normalize_views", "Views normalization")}
            {num("trend", "normalize_likes", "Likes normalization")}
            {num("trend", "growth_full_at_percent", "Full growth score at (%/h)")}
            {num("trend", "freshness_half_life_hours", "Freshness half-life (h)")}
          </div>
        </div>

        <div className="panel p-4">
          <h3 className="text-sm text-gray-400 mb-4">🚀 Publishing</h3>
          <div>
            <label className="label">Mode</label>
            <select
              className="input"
              value={form.publishing.mode ?? "dry_run"}
              onChange={(e) => setForm({ ...form, publishing: { ...form.publishing, mode: e.target.value } })}
            >
              <option value="dry_run">dry_run — simulate end-to-end (safe)</option>
              <option value="live">live — official platform APIs</option>
            </select>
          </div>
          <div className="grid sm:grid-cols-2 gap-3 mt-3">
            {num("publishing", "backoff_base_minutes", "Backoff base (min)", "exponential: base × 2^attempt")}
            {num("publishing", "rate_limit_cooldown_minutes", "Rate-limit cooldown (min)")}
          </div>
          <label className="flex items-center gap-2 mt-3 text-sm text-gray-300">
            <input
              type="checkbox" checked={!!form.publishing.notify_success}
              onChange={(e) => setForm({ ...form, publishing: { ...form.publishing, notify_success: e.target.checked } })}
            />
            Telegram notification on success
          </label>
          <label className="flex items-center gap-2 mt-2 text-sm text-gray-300">
            <input
              type="checkbox" checked={!!form.publishing.notify_failed}
              onChange={(e) => setForm({ ...form, publishing: { ...form.publishing, notify_failed: e.target.checked } })}
            />
            Telegram notification on failure
          </label>
          <div className="mt-3 text-xs text-gray-500 bg-panel2 rounded-lg p-3">
            🛟 The scheduler respects official platform limits: it pauses on
            rate-limit responses, stops accounts on auth errors, and retries
            transient failures with exponential backoff.
          </div>
        </div>

        <div className="panel p-4">
          <h3 className="text-sm text-gray-400 mb-4">🔔 Notifications & discovery</h3>
          <div className="grid sm:grid-cols-2 gap-3">
            {num("notifications", "trend_hot_min_score", "🔥 High-trend alert score")}
            {num("notifications", "milestone_follower_step", "Milestone step (followers)")}
            {num("notifications", "daily_report_hour", "Daily report hour (UTC)")}
            {num("discovery", "max_age_filter_hours", "Discovery max age (h)")}
          </div>
          <label className="flex items-center gap-2 mt-4 text-sm text-gray-300">
            <input
              type="checkbox" checked={!!form.discovery.agent_reach_enabled}
              onChange={(e) => setForm({ ...form, discovery: { ...form.discovery, agent_reach_enabled: e.target.checked } })}
            />
            Allow Agent-Reach provider (experimental — optional)
          </label>
          <p className="text-[10px] text-gray-600 mt-1">
            Also requires MEMES_AGENT_REACH_ENABLED=true and the agent-reach CLI installed. RSS
            works fully without it.
          </p>
        </div>
      </div>
    </div>
  );
}
