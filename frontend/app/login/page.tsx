"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, setToken } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"login" | "register">("login");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const path = mode === "login" ? "/auth/login" : "/auth/register";
      const data = await api.post(path, { email, password });
      setToken(data.access_token);
      router.replace("/");
    } catch (err: any) {
      setError(
        mode === "register" && err.status === 403
          ? "Registration is closed — an owner already exists. Sign in instead."
          : err.message
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="text-5xl mb-3">🤖</div>
          <h1 className="text-2xl font-bold text-white">Memes Pages</h1>
          <p className="text-sm text-gray-500 mt-1">
            Content discovery & publishing automation
          </p>
        </div>
        <form onSubmit={submit} className="panel p-6 space-y-4">
          <div>
            <label className="label">Email</label>
            <input
              className="input" type="email" required value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="admin@example.com"
            />
          </div>
          <div>
            <label className="label">Password</label>
            <input
              className="input" type="password" required minLength={6}
              value={password} onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>
          {error && (
            <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
              {error}
            </div>
          )}
          <button className="btn-primary w-full justify-center py-2.5" disabled={busy}>
            {busy ? "…" : mode === "login" ? "Sign in" : "Create owner account"}
          </button>
          <button
            type="button"
            className="w-full text-xs text-gray-500 hover:text-gray-300"
            onClick={() => setMode(mode === "login" ? "register" : "login")}
          >
            {mode === "login"
              ? "First time? Create the owner account"
              : "← Back to sign in"}
          </button>
        </form>
        <p className="text-center text-xs text-gray-600 mt-6">
          🤖 Telegram bot and worker share this database — configure them via .env
        </p>
      </div>
    </div>
  );
}
