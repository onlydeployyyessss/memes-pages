"use client";

import { useState } from "react";
import { ErrorNote, PageHead } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";

export default function CaptionsPage() {
  const caps = useApi<any>("/captions");
  const tpl = useApi<any>("/captions/templates");
  const [newCap, setNewCap] = useState({ name: "", text: "", hashtags: "" });
  const [newTpl, setNewTpl] = useState({ name: "", template_text: "", weight: 1 });
  const [error, setError] = useState("");

  async function createCaption(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.post("/captions", {
        name: newCap.name,
        text: newCap.text,
        hashtags: newCap.hashtags.split(",").map((x) => x.trim().replace(/^#/, "")).filter(Boolean),
        is_default: false,
      });
      setNewCap({ name: "", text: "", hashtags: "" });
      caps.reload();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function createTemplate(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.post("/captions/templates", {
        name: newTpl.name,
        template_text: newTpl.template_text,
        weight: Number(newTpl.weight) || 1,
        enabled: true,
        placeholder_keys: [],
      });
      setNewTpl({ name: "", template_text: "", weight: 1 });
      tpl.reload();
    } catch (err: any) {
      setError(err.message);
    }
  }

  return (
    <div>
      <PageHead
        title="📝 Captions & Templates"
        desc="Default captions, weighted-random templates with {title}/{hashtags} placeholders, and optional AI tools"
      />
      {error && <ErrorNote msg={error} />}
      {(caps.error || tpl.error) && <ErrorNote msg={caps.error ?? tpl.error ?? ""} />}

      <AIGenerator onDone={() => {}} />

      <div className="grid lg:grid-cols-2 gap-4">
        <div className="panel p-4">
          <h3 className="text-sm text-gray-400 mb-3">📝 Captions</h3>
          <div className="space-y-2">
            {(caps.data?.items ?? []).map((c: any) => (
              <div key={c.id} className="bg-panel2 border border-line rounded-lg p-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-white">
                    {c.name} {c.is_default && <span className="badge ml-1">default</span>}
                  </span>
                  <div className="flex gap-1">
                    {!c.is_default && (
                      <button className="btn-ghost text-xs"
                        onClick={async () => { await api.post(`/captions/${c.id}/make-default`); caps.reload(); }}>
                        ★ default
                      </button>
                    )}
                    <button className="btn-danger text-xs"
                      onClick={async () => { if (confirm(`Delete ${c.name}?`)) { await api.del(`/captions/${c.id}`); caps.reload(); } }}>
                      🗑
                    </button>
                  </div>
                </div>
                <pre className="text-xs text-gray-400 whitespace-pre-wrap mt-2">{c.text}</pre>
                {(c.hashtags ?? []).length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {c.hashtags.map((t: string) => <span key={t} className="badge">#{t}</span>)}
                  </div>
                )}
              </div>
            ))}
            {!caps.data?.items?.length && <p className="text-sm text-gray-500">No captions yet.</p>}
          </div>
          <form onSubmit={createCaption} className="mt-4 space-y-2 border-t border-line pt-4">
            <input className="input" required placeholder="Caption name" value={newCap.name}
              onChange={(e) => setNewCap({ ...newCap, name: e.target.value })} />
            <textarea className="input h-16" placeholder="Caption text — supports {hashtags}"
              value={newCap.text} onChange={(e) => setNewCap({ ...newCap, text: e.target.value })} />
            <input className="input" placeholder="hashtags, comma, separated" value={newCap.hashtags}
              onChange={(e) => setNewCap({ ...newCap, hashtags: e.target.value })} />
            <button className="btn-primary w-full justify-center">+ Add caption</button>
          </form>
        </div>

        <div className="panel p-4">
          <h3 className="text-sm text-gray-400 mb-3">🧩 Templates <span className="text-gray-600">(weighted random per post)</span></h3>
          <div className="space-y-2">
            {(tpl.data?.items ?? []).map((t: any) => (
              <div key={t.id} className="bg-panel2 border border-line rounded-lg p-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-white">{t.name}</span>
                  <div className="flex items-center gap-1">
                    <span className="badge">weight {t.weight}</span>
                    <button className="btn-danger text-xs"
                      onClick={async () => { if (confirm(`Delete ${t.name}?`)) { await api.del(`/captions/templates/${t.id}`); tpl.reload(); } }}>
                      🗑
                    </button>
                  </div>
                </div>
                <pre className="text-xs text-gray-400 whitespace-pre-wrap mt-2">{t.template_text}</pre>
              </div>
            ))}
            {!tpl.data?.items?.length && <p className="text-sm text-gray-500">No templates yet.</p>}
          </div>
          <form onSubmit={createTemplate} className="mt-4 space-y-2 border-t border-line pt-4">
            <input className="input" required placeholder="Template name" value={newTpl.name}
              onChange={(e) => setNewTpl({ ...newTpl, name: e.target.value })} />
            <textarea className="input h-20" placeholder={"Template — placeholders: {title} {author} {account} {hashtags}"}
              value={newTpl.template_text} onChange={(e) => setNewTpl({ ...newTpl, template_text: e.target.value })} />
            <input className="input w-24" type="number" min={1} placeholder="weight" value={newTpl.weight}
              onChange={(e) => setNewTpl({ ...newTpl, weight: +e.target.value })} />
            <button className="btn-primary w-full justify-center">+ Add template</button>
          </form>
        </div>
      </div>
    </div>
  );
}

function AIGenerator({ onDone }: { onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("Funny cat slipping on ice 🐱");
  const [tone, setTone] = useState("fun, casual");
  const [count, setCount] = useState(3);
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState<string[]>([]);
  const [tags, setTags] = useState<string[]>([]);
  const [err, setErr] = useState("");

  async function run(kind: "captions" | "hashtags") {
    setBusy(true);
    setErr("");
    setResults([]);
    setTags([]);
    try {
      if (kind === "captions") {
        const r = await api.post("/ai/captions/generate", { title, tone, count });
        setResults(r.captions ?? []);
        if (!r.captions?.length) setErr("AI returned no captions (check 🤖 AI settings / budget)");
      } else {
        const r = await api.post("/ai/hashtags", { title, count: 12 });
        setTags(r.hashtags ?? []);
        if (!r.hashtags?.length) setErr("AI returned no hashtags (check 🤖 AI settings / budget)");
      }
      onDone();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel p-4 mb-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm text-gray-400">🧠 AI caption tools <span className="text-gray-600">(OpenRouter — optional)</span></h3>
        <button className="btn-ghost" onClick={() => setOpen(!open)}>{open ? "▲" : "▼"}</button>
      </div>
      {open && (
        <div className="mt-3 space-y-3">
          <div className="grid sm:grid-cols-3 gap-2">
            <input className="input sm:col-span-2" placeholder="Video title / idea" value={title} onChange={(e) => setTitle(e.target.value)} />
            <input className="input" placeholder="Tone" value={tone} onChange={(e) => setTone(e.target.value)} />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <input className="input w-24" type="number" min={1} max={10} value={count} onChange={(e) => setCount(+e.target.value)} />
            <button className="btn-primary" disabled={busy} onClick={() => run("captions")}>{busy ? "…" : "✍️ Generate captions"}</button>
            <button className="btn-ghost" disabled={busy} onClick={() => run("hashtags")}>{busy ? "…" : "#️⃣ Generate hashtags"}</button>
            <span className="text-xs text-gray-600">Also available per-account: “AI captions” toggle on Accounts</span>
          </div>
          {err && <div className="text-xs text-red-300">⚠️ {err}</div>}
          {results.length > 0 && (
            <div className="space-y-2">
              {results.map((c, i) => (
                <div key={i} className="bg-panel2 border border-line rounded-lg p-3 text-sm text-gray-300 whitespace-pre-wrap">
                  {c}
                </div>
              ))}
            </div>
          )}
          {tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {tags.map((t) => <span key={t} className="badge">#{t}</span>)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
