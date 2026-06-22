"use client";

import { Suspense } from "react";

import { useSearchParams } from "next/navigation";

import type { AnalyticsTab } from "@/features/analytics/types";
import { AnalyticsCoverageTab } from "@/features/analytics/components/AnalyticsCoverageTab";
import { AnalyticsComparisonsTab } from "@/features/analytics/components/AnalyticsComparisonsTab";
import { AnalyticsOlapTab } from "@/features/analytics/components/AnalyticsOlapTab";
import { AnalyticsOverviewTab } from "@/features/analytics/components/AnalyticsOverviewTab";
import { AnalyticsSuperlativesTab } from "@/features/analytics/components/AnalyticsSuperlativesTab";
import { AnalyticsTabs } from "@/features/analytics/components/AnalyticsTabs";
import { AnalyticsTrendsTab } from "@/features/analytics/components/AnalyticsTrendsTab";
import { LoadingSkeleton } from "@/shared/components/feedback/LoadingSkeleton";
import {
  ProfilePanel,
  ProfileShell,
  ProfileTag,
} from "@/shared/components/profile/ProfilePrimitives";

const VALID_TABS: AnalyticsTab[] = ["overview", "trends", "olap", "comparisons", "superlatives", "coverage"];

function normalizeTab(value: string | null): AnalyticsTab {
  return VALID_TABS.includes(value as AnalyticsTab) ? (value as AnalyticsTab) : "overview";
}

function ActiveTabContent({ tab }: { tab: AnalyticsTab }) {
  switch (tab) {
    case "overview":
      return <AnalyticsOverviewTab />;
    case "trends":
      return <AnalyticsTrendsTab />;
    case "olap":
      return <AnalyticsOlapTab />;
    case "comparisons":
      return <AnalyticsComparisonsTab />;
    case "superlatives":
      return <AnalyticsSuperlativesTab />;
    case "coverage":
      return <AnalyticsCoverageTab />;
    default:
      return <AnalyticsOverviewTab />;
  }
}

function AnalyticsPageContentInner() {
  const searchParams = useSearchParams();
  const activeTab = normalizeTab(searchParams.get("tab"));

  return (
    <ProfileShell className="space-y-6">
      <ProfilePanel className="overflow-hidden p-0" tone="accent">
        <div className="grid gap-5 p-5 md:p-6 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.36fr)] xl:items-end">
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <ProfileTag>Data Warehouse</ProfileTag>
              <ProfileTag>OLAP</ProfileTag>
              <ProfileTag>Slice and Dice</ProfileTag>
            </div>
            <div>
              <p className="text-[0.68rem] font-bold uppercase tracking-[0.18em] text-white/58">
                Destaques Analíticos
              </p>
              <h1 className="mt-2 max-w-4xl font-[family:var(--font-profile-headline)] text-3xl font-extrabold leading-[0.98] tracking-[-0.035em] text-white md:text-5xl">
                Tendências, agregações e comparações do recorte atual
              </h1>
              <p className="mt-3 max-w-3xl text-sm/6 font-medium text-white/70">
                A página concentra operações OLAP, séries temporais, superlativos derivados e cobertura para validar o que o dado realmente sustenta.
              </p>
            </div>
          </div>

          <div className="rounded-xl border border-white/12 bg-white/8 p-4 text-sm/6 font-medium text-white/72">
            Use os filtros globais para mudar competição, temporada, rodada, mando e período. As abas reaproveitam o mesmo escopo para manter os números comparáveis.
          </div>
        </div>
      </ProfilePanel>

      <AnalyticsTabs />

      <Suspense fallback={<LoadingSkeleton height={200} />}>
        <ActiveTabContent tab={activeTab} />
      </Suspense>
    </ProfileShell>
  );
}

export function AnalyticsPageContent() {
  return (
    <Suspense
      fallback={
        <div className="space-y-4">
          <LoadingSkeleton height={40} />
          <LoadingSkeleton height={200} />
        </div>
      }
    >
      <AnalyticsPageContentInner />
    </Suspense>
  );
}
