"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { clsx } from "clsx";
import * as api from "@/lib/api";

const PUBLIC_NAV = [
  { href: "/", label: "Home" },
  { href: "/models", label: "Models" },
  { href: "/estimate", label: "Cost Calculator" },
  { href: "/pricing", label: "Pricing" },
];

const AUTH_NAV = [
  { href: "/builder", label: "Builder" },
  { href: "/playground", label: "Playground" },
  { href: "/deploy", label: "Deploy" },
  { href: "/managed", label: "Managed" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/settings/alerts", label: "Alerts" },
  { href: "/settings/credentials", label: "Credentials" },
];

const TIER_BADGES: Record<string, { label: string; classes: string }> = {
  free: { label: "FREE", classes: "bg-gray-800 text-gray-400 border-gray-700" },
  pro: { label: "PRO", classes: "bg-blue-900/40 text-blue-400 border-blue-800" },
  enterprise: { label: "ENTERPRISE", classes: "bg-purple-900/40 text-purple-400 border-purple-800" },
};

export function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [loggedIn, setLoggedIn] = useState(false);
  const [tier, setTier] = useState<string | null>(null);

  useEffect(() => {
    const isAuth = api.isAuthenticated();
    setLoggedIn(isAuth);
    if (isAuth) {
      api.getSubscriptionStatus().then((s) => setTier(s.tier)).catch(() => {});
    } else {
      setTier(null);
    }
  }, [pathname]);

  function handleLogout() {
    api.logout();
    setLoggedIn(false);
    router.push("/");
  }

  const navItems = loggedIn ? [...PUBLIC_NAV, ...AUTH_NAV] : PUBLIC_NAV;

  return (
    <nav className="border-b border-gray-800 bg-gray-900/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
        <Link href="/" className="text-lg font-bold text-white">
          <span className="text-brand-400">LLM</span> Cloud Platform
        </Link>
        <div className="flex items-center gap-1">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "rounded-lg px-3 py-1.5 text-sm font-medium transition",
                pathname === item.href
                  ? "bg-brand-600/20 text-brand-400"
                  : "text-gray-400 hover:text-gray-200 hover:bg-gray-800"
              )}
            >
              {item.label}
            </Link>
          ))}

          <span className="mx-2 h-5 w-px bg-gray-700" />

          {loggedIn ? (
            <div className="flex items-center gap-2">
              {tier && TIER_BADGES[tier] && (
                <Link
                  href="/pricing"
                  className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase hover:opacity-80 transition ${TIER_BADGES[tier].classes}`}
                  title="Manage subscription"
                >
                  {TIER_BADGES[tier].label}
                </Link>
              )}
              <button
                onClick={handleLogout}
                className="rounded-lg px-3 py-1.5 text-sm font-medium text-gray-400 hover:text-red-400 hover:bg-gray-800 transition"
              >
                Sign Out
              </button>
            </div>
          ) : (
            <Link
              href="/auth"
              className={clsx(
                "rounded-lg px-3 py-1.5 text-sm font-medium transition",
                pathname === "/auth"
                  ? "bg-brand-600 text-white"
                  : "bg-brand-600/80 text-white hover:bg-brand-600"
              )}
            >
              Sign In
            </Link>
          )}
        </div>
      </div>
    </nav>
  );
}
