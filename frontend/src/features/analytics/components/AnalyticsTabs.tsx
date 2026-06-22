"use client";

import { useCallback } from "react";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

import type { AnalyticsTab } from "@/features/analytics/types";

const TABS: Array<{ key: AnalyticsTab; label: string }> = [
  { key: "overview", label: "Resumo" },
  { key: "trends", label: "Tendências" },
  { key: "olap", label: "OLAP" },
  { key: "comparisons", label: "Comparações" },
  { key: "superlatives", label: "Superlativos" },
  { key: "coverage", label: "Cobertura" },
];

function isAnalyticsTab(value: string | null): value is AnalyticsTab {
  return TABS.some((tab) => tab.key === value);
}

export function AnalyticsTabs() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();
  const rawTab = searchParams.get("tab");
  const activeTab: AnalyticsTab = isAnalyticsTab(rawTab) ? rawTab : "overview";

  const handleTabClick = useCallback(
    (tab: AnalyticsTab) => {
      const params = new URLSearchParams(searchParams.toString());
      if (tab === "overview") {
        params.delete("tab");
      } else {
        params.set("tab", tab);
      }
      const queryString = params.toString();
      router.push(queryString ? `${pathname}?${queryString}` : pathname);
    },
    [pathname, router, searchParams],
  );

  return (
    <nav
      aria-label="Abas de análise"
      className="rounded-xl border border-[rgba(191,201,195,0.34)] bg-[rgba(240,243,255,0.72)] p-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.74)]"
    >
      <div className="flex gap-2 overflow-x-auto">
        {TABS.map((tab) => {
          const isActive = activeTab === tab.key;
          return (
            <button
              className={
                isActive
                  ? "button-pill button-pill-primary whitespace-nowrap"
                  : "button-pill button-pill-secondary whitespace-nowrap"
              }
              key={tab.key}
              onClick={() => handleTabClick(tab.key)}
              type="button"
              aria-current={isActive ? "page" : undefined}
            >
              {tab.label}
            </button>
          );
        })}
      </div>
    </nav>
  );
}
