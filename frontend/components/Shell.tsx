"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, clearToken, getToken } from "@/lib/api";

const NAV = [
  { href: "/", label: "Overview", icon: "📊" },
  { href: "/accounts", label: "Accounts", icon: "📱" },
  { href: "/trending", label: "Trending", icon: "🔥" },
  { href: "/sources", label: "Sources", icon: "📡" },
  { href: "/content", label: "Content", icon: "🎬" },
  { href: "/queue", label: "Queue", icon: "📥" },
  { href: "/schedule", label: "Schedule", icon: "📅" },
  { href: "/analytics", label: "Analytics", icon: "📈" },
  { href: "/reports", label: "Reports", icon: "📄" },
  { href: "/settings", label: "Settings", icon: "⚙️" },
];

export default function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [open, setOpen] = useState(false);
  const [me, setMe] = useState<any>(null);
  const isLogin = pathname === "/login";

  useEffect(() => {
    if (isLogin) { setReady(true); return; }
    if (!getToken()) { router.replace("/login"); return; }
    api.get("/auth/me")
      .then((data) => { setMe(data); setReady(true); })
      .catch(() => {});
  }, [isLogin, pathname, router]);

  if (isLogin) return <>{children}</>;
  if (!ready) {
    return (
      <div className="min-h-screen flex items-center justify-center text-gray-500">
        🤖 Loading Memes Pages…
      </div>
    );
  }

  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <aside
        className={`fixed lg:static z-40 inset-y-0 left-0 w-60 bg-panel border-r border-line
          transform transition-transform lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}
      >
        <div className="h-16 flex items-center gap-2 px-5 border-b border-line">
          <span className="text-2xl">🤖</span>
          <div>
            <div className="font-semibold text-white leading-tight">Memes Pages</div>
            <div className="text-[10px] text-gray-500 uppercase tracking-widest">Agent Platform</div>
          </div>
        </div>
        <nav className="p-3 space-y-0.5 overflow-y-auto" style={{ maxHeight: "calc(100vh - 4rem)" }}>
          {NAV.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors
                  ${active ? "bg-accent/15 text-white border border-accent/30" : "text-gray-400 hover:bg-panel2 hover:text-gray-200 border border-transparent"}`}
              >
                <span>{item.icon}</span> {item.label}
              </Link>
            );
          })}
          <div className="pt-3 mt-3 border-t border-line">
            <button
              onClick={() => { clearToken(); router.push("/login"); }}
              className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-gray-500 hover:text-red-300 hover:bg-red-500/10"
            >
              🚪 Sign out
            </button>
          </div>
        </nav>
      </aside>

      {open && (
        <div className="fixed inset-0 bg-black/60 z-30 lg:hidden" onClick={() => setOpen(false)} />
      )}

      {/* Main */}
      <div className="flex-1 min-w-0">
        <header className="h-16 border-b border-line bg-panel/60 backdrop-blur sticky top-0 z-20 flex items-center justify-between px-4 lg:px-8">
          <div className="flex items-center gap-3">
            <button className="lg:hidden btn-ghost" onClick={() => setOpen(true)}>☰</button>
            <h1 className="text-sm text-gray-400">
              {NAV.find((n) => n.href === pathname)?.label ?? "Memes Pages"}
            </h1>
          </div>
          <div className="flex items-center gap-3">
            <span className="badge hidden sm:inline-flex">🟢 API</span>
            <span className="text-xs text-gray-500">{me?.email}</span>
            <span className="w-8 h-8 rounded-full bg-accent/20 border border-accent/40 flex items-center justify-center text-sm">
              {(me?.email ?? "?")[0].toUpperCase()}
            </span>
          </div>
        </header>
        <main className="p-4 lg:p-8 max-w-7xl mx-auto">{children}</main>
      </div>
    </div>
  );
}
