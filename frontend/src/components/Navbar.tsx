"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, useRef } from "react";
import { clsx } from "clsx";
import * as api from "@/lib/api";

const PUBLIC_NAV = [
  { href: "/", label: "Home" },
  { href: "/models", label: "Models" },
  { href: "/estimate", label: "Cost Calculator" },
  { href: "/compare", label: "Compare" },
  { href: "/infra", label: "Infra Agent" },
  { href: "/recommend", label: "Recommend" },
  { href: "/pricing", label: "Pricing" },
];

const AUTH_NAV_GROUPS = [
  {
    label: "Tools",
    items: [
      { href: "/builder", label: "Builder" },
      { href: "/playground", label: "Playground" },
      { href: "/deploy", label: "Deploy" },
      { href: "/managed", label: "Managed" },
    ],
  },
  {
    label: "Settings",
    items: [
      { href: "/dashboard", label: "Dashboard" },
      { href: "/workflow", label: "Workflow" },
      { href: "/settings/alerts", label: "Alerts" },
      { href: "/settings/credentials", label: "Credentials" },
    ],
  },
];

const AUTH_NAV_FLAT = AUTH_NAV_GROUPS.flatMap((g) => g.items);

const TIER_BADGES: Record<string, { label: string; classes: string }> = {
  free: { label: "FREE", classes: "bg-gray-800 text-gray-400 border-gray-700" },
  pro: { label: "PRO", classes: "bg-blue-900/40 text-blue-400 border-blue-800" },
  enterprise: { label: "ENTERPRISE", classes: "bg-purple-900/40 text-purple-400 border-purple-800" },
};

function Dropdown({ label, items, pathname }: { label: string; items: { href: string; label: string }[]; pathname: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const isActive = items.some((i) => pathname === i.href);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  useEffect(() => { setOpen(false); }, [pathname]);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={clsx(
          "flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm font-medium transition",
          isActive ? "bg-brand-600/20 text-brand-400" : "text-gray-400 hover:text-gray-200 hover:bg-gray-800"
        )}
      >
        {label}
        <svg className={clsx("h-3 w-3 transition-transform", open && "rotate-180")} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 w-44 rounded-lg border border-gray-700 bg-gray-900 py-1 shadow-xl z-50">
          {items.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "block px-4 py-2 text-sm transition",
                pathname === item.href ? "bg-brand-600/20 text-brand-400" : "text-gray-300 hover:bg-gray-800 hover:text-white"
              )}
            >
              {item.label}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

export function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [loggedIn, setLoggedIn] = useState(false);
  const [tier, setTier] = useState<string | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const isAuth = api.isAuthenticated();
    setLoggedIn(isAuth);
    if (isAuth) {
      api.getSubscriptionStatus().then((s) => setTier(s.tier)).catch(() => {});
    } else {
      setTier(null);
    }
  }, [pathname]);

  useEffect(() => { setMobileOpen(false); }, [pathname]);

  function handleLogout() {
    api.logout();
    setLoggedIn(false);
    router.push("/");
  }

  const allFlat = loggedIn ? [...PUBLIC_NAV, ...AUTH_NAV_FLAT] : PUBLIC_NAV;

  return (
    <nav className="border-b border-gray-800 bg-gray-900/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
        {/* Logo */}
        <Link href="/" className="text-lg font-bold text-white shrink-0">
          <span className="text-brand-400">LLM</span> Cloud Platform
        </Link>

        {/* Desktop nav */}
        <div className="hidden lg:flex items-center gap-1">
          {PUBLIC_NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "rounded-lg px-3 py-1.5 text-sm font-medium transition whitespace-nowrap",
                pathname === item.href
                  ? "bg-brand-600/20 text-brand-400"
                  : "text-gray-400 hover:text-gray-200 hover:bg-gray-800"
              )}
            >
              {item.label}
            </Link>
          ))}

          {loggedIn && (
            <>
              <span className="mx-1 h-5 w-px bg-gray-700" />
              {AUTH_NAV_GROUPS.map((group) => (
                <Dropdown key={group.label} label={group.label} items={group.items} pathname={pathname} />
              ))}
            </>
          )}

          <span className="mx-1 h-5 w-px bg-gray-700" />

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

        {/* Mobile hamburger */}
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="lg:hidden rounded-lg p-2 text-gray-400 hover:bg-gray-800 hover:text-white transition"
        >
          {mobileOpen ? (
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          ) : (
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          )}
        </button>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="lg:hidden border-t border-gray-800 bg-gray-900 px-4 py-3 space-y-1 max-h-[80vh] overflow-y-auto">
          {allFlat.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "block rounded-lg px-3 py-2 text-sm font-medium transition",
                pathname === item.href
                  ? "bg-brand-600/20 text-brand-400"
                  : "text-gray-400 hover:text-gray-200 hover:bg-gray-800"
              )}
            >
              {item.label}
            </Link>
          ))}
          <div className="pt-2 border-t border-gray-800">
            {loggedIn ? (
              <div className="flex items-center gap-3 px-3 py-2">
                {tier && TIER_BADGES[tier] && (
                  <Link
                    href="/pricing"
                    className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase hover:opacity-80 transition ${TIER_BADGES[tier].classes}`}
                  >
                    {TIER_BADGES[tier].label}
                  </Link>
                )}
                <button
                  onClick={handleLogout}
                  className="text-sm font-medium text-gray-400 hover:text-red-400 transition"
                >
                  Sign Out
                </button>
              </div>
            ) : (
              <Link
                href="/auth"
                className="block rounded-lg px-3 py-2 text-sm font-medium bg-brand-600/80 text-white hover:bg-brand-600 transition text-center"
              >
                Sign In
              </Link>
            )}
          </div>
        </div>
      )}
    </nav>
  );
}
