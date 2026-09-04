"use client";

import { useCallback, useEffect, useState } from "react";
import { ErrorNote, PageHead } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtInt, useApi } from "@/lib/hooks";

export default function AIPage() {
  const status = useApi<any>("/ai/status");
  const [form, setForm] = useState<any>(null);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<any>(null);
  const [savedMsg, setSavedMsg] = useState("");
  const [customModel, setCustomModel] = useState("");

  useEffect(() => {
    if (status.data && form === null) setForm({ ...status.data });
  }, [status.data, form]);

  const save = useCallback(async () => {
    setSavedMsg("");
    try {
      await api.put("/ai/settings", {
        enabled: form.enabled,
        model: form.model,
        trend_assist: form.features.trend_assist,
        influence_scoring: form.features.influence_scoring,
        blend_weight: Number(form.blend_weight ?? 0.3),
        max_score_adjustment: Number(form.max_score_adjustment ?? 10),
        caption_generation: form.features.caption_generation,
        report_summaries: form.features.report_summaries,
        assistant_enabled: form.features.assistant_enabled,
        max_requests_per_hour: Number(form.limits.max_requests_per_hour ?? 30),
        max_requests_per_day: Number(form.limits.max_requests_per_day ?? 300),
      });
      setSavedMsg("✅ Saved");
      setTimeout(() => setSavedMsg(""), 2000);
      status.reload();
    } catch (e: any) {
      setSavedMsg(`⚠️ ${e.message}`);
    }
  }, [form, status]);

  async function testConnection() {
    setTesting(true);
    setTestResult(null);
    try {
      setTestResult(await api.post("/ai/test"));
    } catch (e: any) {
      setTestResult({ ok: false, message: e.message });
    } finally {
      setTesting(false);
      status.reload();
    }
  }

  if (status.error) return <ErrorNote msg={status.error} />;
  if (!form) return <p className="text-gray-500 text-sm">Loading AI settings…</p>;

  const connected = form.key_configured && form.enabled;

  return (
    <div>
      <PageHead
        title="🤖 AI Settings"
        desc="OpenRouter powers Trend Hunter analysis, captions, reports and the Telegram assistant"
        actions={
          <>
            {savedMsg && <span className="text-sm text-gray-400">{savedMsg}</span>}
            <button className="btn-ghost" disabled={testing} onClick={testConnection}>
              {testing ? "Testing…" : "🔌 Test Connection"}
            </button>
            <button className="btn-primary" onClick={save}>💾 Save</button>
          </>
        }
      />

      {testResult && (
        <div
          className={`rounded-lg border px-4 py-3 text-sm mb-4 ${
            testResult.ok
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
              : "border-red-500/30 bg-red-500/10 text-red-300"
          }`}
        >
          {testResult.message}
          {testResult.latency_ms != null && testResult.ok && (
            <span className="text-gray-400"> · {testResult.latency_ms} ms</span>
          )}
        </div>
      )}

      <div className="grid lg:grid-cols-2 gap-4">
        {/* Provider & status */}
        <div className="panel p-4">
          <h3 className="text-sm text-gray-400 mb-4">🔑 Provider</h3>
          <div className="space-y-2 text-sm">
            <Row k="Provider" v="OpenRouter" />
            <Row
              k="AI Status"
              v={
                connected ? (
                  <span className="text-emerald-300">🟢 Connected</span>
                ) : form.key_configured ? (
                  <span className="text-amber-300">🟡 Key set — AI disabled</span>
                ) : (
                  <span className="text-gray-400">⚪ Not configured</span>
                )
              }
            />
            <Row
              k="API key"
              v={form.key_configured ? "🔐 configured (hidden)" : "— set OPENROUTER_API_KEY"}
            />
            <Row k="Requests today" v={`${fmtInt(form.requests_today)} / ${fmtInt(form.limits?.max_requests_per_day ?? 0)}`} />
            <Row k="Requests this hour" v={`${fmtInt(form.requests_this_hour)} / ${fmtInt(form.limits?.max_requests_per_hour ?? 0)}`} />
            <Row k="Token usage today" v={`${fmtInt(form.tokens_today)} tokens`} />
            {form.last_error && (
              <Row
                k="Last error"
                v={<span className="text-red-300">{form.last_error.error_type}: {form.last_error.error}</span>}
              />
            )}
          </div>
          <p className="text-[10px] text-gray-600 mt-3">
            The API key lives only in the server environment (env var /
            Railway secret). It is never displayed, logged, or sent to this
            dashboard.
          </p>
        </div>

        {/* Model & cost controls */}
        <div className="panel p-4">
          <h3 className="text-sm text-gray-400 mb-4">🧠 Model & cost controls</h3>
          <label className="label">Model</label>
          <select
            className="input"
            value={form.available_models?.includes(form.model) ? form.model : "__custom"}
            onChange={(e) => {
              if (e.target.value !== "__custom") setForm({ ...form, model: e.target.value });
              else setCustomModel("custom-model:free");
            }}
          >
            {(form.available_models ?? []).map((m: string) => (
              <option key={m} value={m}>{m}</option>
            ))}
            {!form.available_models?.includes(form.model) && (
              <option value="__custom">{form.model} (custom)</option>
            )}
          </select>
          {form.available_models?.includes("liquid/lfm-2.5-embedding-350m:free") && (
            <p className="text-[10px] text-amber-400/70 mt-1">
              ⚠️ liquid/lfm-2.5-embedding-350m:free is an embedding model — chat
              features will fail with it (fallback keeps automation running).
            </p>
          )}
          {form.available_models && !form.available_models.includes(form.model) && (
            <input className="input mt-2" value={form.model}
              onChange={(e) => setForm({ ...form, model: e.target.value })} />
          )}
          <div className="grid grid-cols-2 gap-3 mt-3">
            <div>
              <label className="label">Max requests / hour</label>
              <input className="input" type="number" min={0}
                value={form.limits?.max_requests_per_hour ?? 30}
                onChange={(e) => setForm({ ...form, limits: { ...form.limits, max_requests_per_hour: +e.target.value } })} />
            </div>
            <div>
              <label className="label">Max requests / day</label>
              <input className="input" type="number" min={0}
                value={form.limits?.max_requests_per_day ?? 300}
                onChange={(e) => setForm({ ...form, limits: { ...form.limits, max_requests_per_day: +e.target.value } })} />
            </div>
            <div>
              <label className="label">Score blend weight (0–1)</label>
              <input className="input" type="number" step="0.05" min={0} max={1}
                value={form.features?.influence_scoring ? (form.blend_weight ?? 0.3) : 0}
                disabled={!form.features?.influence_scoring}
                onChange={(e) => setForm({ ...form, blend_weight: +e.target.value })} />
            </div>
            <div>
              <label className="label">Max score adjustment</label>
              <input className="input" type="number" min={0} max={50}
                value={form.max_score_adjustment ?? 10}
                onChange={(e) => setForm({ ...form, max_score_adjustment: +e.target.value })} />
            </div>
          </div>
          <p className="text-[10px] text-gray-600 mt-2">
            Token & timeout limits also come from env:
            OPENROUTER_MAX_TOKENS (default 1000), OPENROUTER_TIMEOUT (default 30s).
          </p>
        </div>

        {/* Feature toggles */}
        <div className="panel p-4 lg:col-span-2">
          <h3 className="text-sm text-gray-400 mb-4">⚡ AI features (all optional — system works without them)</h3>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3 text-sm">
            <Toggle label="🔥 Trend Hunter AI analysis" hint="Attach structured AI analysis to every scored item"
              checked={form.features?.trend_assist}
              onChange={(v: boolean) => setForm({ ...form, features: { ...form.features, trend_assist: v } })} />
            <Toggle label="⚖️ AI influences trend score" hint="Bounded blend with the deterministic score"
              checked={form.features?.influence_scoring}
              onChange={(v: boolean) => setForm({ ...form, features: { ...form.features, influence_scoring: v } })} />
            <Toggle label="📝 AI captions allowed" hint="Per-account opt-in on the Accounts page"
              checked={form.features?.caption_generation}
              onChange={(v: boolean) => setForm({ ...form, features: { ...form.features, caption_generation: v } })} />
            <Toggle label="📊 AI report summaries" hint="Human-readable summary atop DB-derived reports"
              checked={form.features?.report_summaries}
              onChange={(v: boolean) => setForm({ ...form, features: { ...form.features, report_summaries: v } })} />
            <Toggle label="🤖 Telegram AI assistant" hint="Ask AI about your live analytics"
              checked={form.features?.assistant_enabled}
              onChange={(v: boolean) => setForm({ ...form, features: { ...form.features, assistant_enabled: v } })} />
            <Toggle label="AI master switch" hint="Turn all AI calls off instantly"
              checked={form.enabled}
              onChange={(v: boolean) => setForm({ ...form, enabled: v })} />
          </div>
          <div className="mt-4 text-xs text-gray-500 bg-panel2 rounded-lg p-3">
            🛟 <b>Fallback guarantee:</b> if OpenRouter is unavailable, times out,
            returns malformed JSON, or hits a usage limit — Trend Hunter falls back
            to deterministic scoring (views / engagement / growth velocity / age)
            and the publishing pipeline continues untouched.
          </div>
        </div>
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: any }) {
  return (
    <div className="flex items-center justify-between border-t border-line/60 py-1.5 first:border-0">
      <span className="text-gray-500">{k}</span>
      <span className="text-gray-200 text-right">{v}</span>
    </div>
  );
}

function Toggle({ label, hint, checked, onChange }: {
  label: string; hint: string; checked: boolean; onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-start gap-2 bg-panel2 border border-line rounded-lg p-3 cursor-pointer">
      <input type="checkbox" className="mt-0.5" checked={!!checked} onChange={(e) => onChange(e.target.checked)} />
      <span>
        <span className="text-gray-200">{label}</span>
        <span className="block text-[10px] text-gray-500 mt-0.5">{hint}</span>
      </span>
    </label>
  );
}
