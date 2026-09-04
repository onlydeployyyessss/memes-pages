"use client";

import { useState } from "react";
import { ErrorNote, PageHead, StatusBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate, fmtInt, st, useApi } from "@/lib/hooks";

export default function AccountsPage() {
  const { data, error, reload } = useApi<any>("/accounts");
  const caps = useApi<any>("/captions");
  const covers = useApi<any>("/covers");
  const [creating, setCreating] = useState(false);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [form, setForm] = useState<any>({ name: "", platform: "instagram", username: "" });

  async function create(e: React.FormEvent) {
    e.preventDefault();
    await api.post("/accounts", form);
    setForm({ name: "", platform: "instagram", username: "" });
    setCreating(false);
    reload();
  }

  async function toggle(acc: any) {
    await api.post(`/accounts/${acc.id}/automation`, { enabled: !acc.automation_enabled });
    reload();
  }

  async function saveSettings(acc: any, patch: any) {
    await api.put(`/accounts/${acc.id}/settings`, patch);
    reload();
  }

  async function saveCreds(acc: any, credsText: string) {
    try {
      const creds = JSON.parse(credsText || "{}");
      await api.post(`/accounts/${acc.id}/credentials`, { credentials: creds });
      reload();
    } catch (e: any) {
      alert(`Invalid JSON: ${e.message}`);
    }
  }

  return (
    <div>
      <PageHead
        title="📱 Destination Accounts"
        desc="Multiple accounts with independent caption, cover, schedule and limits"
        actions={<button className="btn-primary" onClick={() => setCreating(!creating)}>+ Add account</button>}
      />
      {error && <ErrorNote msg={error} />}

      {creating && (
        <form onSubmit={create} className="panel p-4 mb-4 grid sm:grid-cols-4 gap-3 items-end">
          <div>
            <label className="label">Name</label>
            <input className="input" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <label className="label">Platform</label>
            <select className="input" value={form.platform} onChange={(e) => setForm({ ...form, platform: e.target.value })}>
              <option value="instagram">Instagram</option>
              <option value="youtube">YouTube (Shorts)</option>
              <option value="tiktok">TikTok (dry-run)</option>
              <option value="custom">Custom / dry-run</option>
            </select>
          </div>
          <div>
            <label className="label">Username</label>
            <input className="input" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
          </div>
          <button className="btn-primary justify-center">Create</button>
        </form>
      )}

      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
        {(data?.items ?? []).map((acc: any) => (
          <div key={acc.id} className="panel p-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <span className="w-10 h-10 rounded-full bg-accent/15 border border-accent/30 flex items-center justify-center text-lg">
                  {acc.platform === "youtube" ? "▶️" : acc.platform === "instagram" ? "📷" : "🤖"}
                </span>
                <div>
                  <div className="font-medium text-white">@{acc.username || acc.name}</div>
                  <div className="text-xs text-gray-500">{acc.platform}</div>
                </div>
              </div>
              <StatusBadge status={acc.status} />
            </div>

            <div className="grid grid-cols-3 gap-2 mt-4 text-center">
              <div className="bg-panel2 rounded-lg py-2">
                <div className="text-lg font-semibold text-white">{fmtInt(acc.followers_count)}</div>
                <div className="text-[10px] text-gray-500 uppercase">Followers</div>
              </div>
              <div className="bg-panel2 rounded-lg py-2">
                <div className="text-lg font-semibold">{acc.automation_enabled ? "🟢 ON" : "🔴 OFF"}</div>
                <div className="text-[10px] text-gray-500 uppercase">Automation</div>
              </div>
              <div className="bg-panel2 rounded-lg py-2">
                <div className="text-lg font-semibold">{st(acc.integration_status)}</div>
                <div className="text-[10px] text-gray-500 uppercase">API</div>
              </div>
            </div>

            <div className="text-xs text-gray-500 mt-3">
              Last post: {fmtDate(acc.last_publish_at)} • Key in:{" "}
              {acc.has_credentials ? "🔐 stored" : "—"}
            </div>

            <div className="flex gap-2 mt-3">
              <button className="btn-ghost flex-1 justify-center" onClick={() => toggle(acc)}>
                {acc.automation_enabled ? "⏸ Pause auto" : "▶ Start auto"}
              </button>
              <button className="btn-ghost flex-1 justify-center"
                onClick={() => setExpanded(expanded === acc.id ? null : acc.id)}>
                ⚙️ Settings
              </button>
              <button className="btn-ghost" onClick={async () => { await api.post(`/accounts/${acc.id}/metrics/refresh`); reload(); }}>
                🔄
              </button>
            </div>

            {expanded === acc.id && (
              <AccountSettingsPanel acc={acc} captions={caps.data?.items ?? []}
                covers={covers.data?.items ?? []}
                onSaveSettings={saveSettings} onSaveCreds={saveCreds}
                onDelete={async () => { if (confirm(`Delete @${acc.username}?`)) { await api.del(`/accounts/${acc.id}`); setExpanded(null); reload(); } }}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function AccountSettingsPanel({ acc, captions, covers, onSaveSettings, onSaveCreds, onDelete }: any) {
  const s = acc.settings ?? {};
  const [capMode, setCapMode] = useState(s.caption_settings?.mode ?? "default");
  const [customText, setCustomText] = useState(s.caption_settings?.custom_text ?? "");
  const [hashtags, setHashtags] = useState((s.caption_settings?.hashtags ?? []).join(", "));
  const [distEnabled, setDistEnabled] = useState(s.distribution?.enabled !== false);
  const [useAi, setUseAi] = useState(!!s.caption_settings?.use_ai);
  const [aiTone, setAiTone] = useState(s.caption_settings?.ai_tone ?? "fun, casual");
  const [maxDay, setMaxDay] = useState(s.posting_limits?.max_per_day ?? 8);
  const [delay, setDelay] = useState(s.distribution?.publish_delay_minutes ?? 0);
  const [creds, setCreds] = useState("{}");

  return (
    <div className="mt-4 border-t border-line pt-4 space-y-3 text-sm">
      <div>
        <label className="label">Caption mode</label>
        <select className="input" value={capMode} onChange={(e) => setCapMode(e.target.value)}>
          <option value="default">Default caption</option>
          <option value="template">Template (random weighted)</option>
          <option value="custom">Custom text</option>
        </select>
      </div>
      {capMode === "custom" && (
        <div>
          <label className="label">Custom caption (supports {"{title}"} {"{hashtags}"})</label>
          <textarea className="input h-20" value={customText} onChange={(e) => setCustomText(e.target.value)} />
        </div>
      )}
      <div>
        <label className="label">Hashtags (comma separated)</label>
        <input className="input" value={hashtags} onChange={(e) => setHashtags(e.target.value)} />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="label">Max posts/day</label>
          <input className="input" type="number" min={1} value={maxDay} onChange={(e) => setMaxDay(+e.target.value)} />
        </div>
        <div>
          <label className="label">Publish delay (min)</label>
          <input className="input" type="number" min={0} value={delay} onChange={(e) => setDelay(+e.target.value)} />
        </div>
      </div>
      <label className="flex items-center gap-2 text-gray-300">
        <input type="checkbox" checked={distEnabled} onChange={(e) => setDistEnabled(e.target.checked)} />
        Receive auto-distributed trending videos
      </label>
      <label className="flex items-center gap-2 text-gray-300">
        <input type="checkbox" checked={useAi} onChange={(e) => setUseAi(e.target.checked)} />
        🧠 AI-generated captions (optional — falls back to the caption above if AI is off)
      </label>
      {useAi && (
        <div>
          <label className="label">AI caption tone</label>
          <input className="input" value={aiTone} onChange={(e) => setAiTone(e.target.value)} />
        </div>
      )}
      <div className="flex gap-2">
        <button className="btn-primary flex-1 justify-center"
          onClick={() => onSaveSettings(acc, {
            caption_settings: { mode: capMode, custom_text: customText, hashtags: hashtags.split(",").map((x) => x.trim().replace(/^#/, "")).filter(Boolean), first_comment: "", use_ai: useAi, ai_tone: aiTone },
            posting_limits: { ...(s.posting_limits ?? {}), max_per_day: maxDay },
            distribution: { ...(s.distribution ?? {}), enabled: distEnabled, publish_delay_minutes: delay },
          })}>
          💾 Save
        </button>
        <button className="btn-danger" onClick={onDelete}>🗑</button>
      </div>
      <div>
        <label className="label">Platform credentials (JSON — stored encrypted)</label>
        <textarea className="input h-16 font-mono text-xs"
          placeholder='{"access_token":"…","ig_user_id":"…"}'
          value={creds} onChange={(e) => setCreds(e.target.value)} />
        <button className="btn-ghost mt-2" onClick={() => onSaveCreds(acc, creds)}>🔐 Store credentials</button>
      </div>
    </div>
  );
}
