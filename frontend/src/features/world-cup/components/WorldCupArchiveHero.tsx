"use client";

import type { ReactNode } from "react";

import Image from "next/image";

import { buildVisualAssetUrl } from "@/shared/components/profile/ProfileMedia";
import { ProfilePanel } from "@/shared/components/profile/ProfilePrimitives";

const WORLD_CUP_HERO_BACKGROUND_KEY = "wc_mens_hero_bg";

function joinClasses(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

export function WorldCupArchiveHero({
  aside,
  asideClassName,
  description,
  footer,
  kicker,
  metrics,
  title,
}: {
  aside?: ReactNode;
  asideClassName?: string;
  description?: ReactNode;
  footer?: ReactNode;
  kicker?: ReactNode;
  metrics?: ReactNode;
  title: ReactNode;
}) {
  const heroBackgroundUrl = buildVisualAssetUrl("competitions", WORLD_CUP_HERO_BACKGROUND_KEY);

  return (
    <ProfilePanel
      className="world-cup-hero relative flex min-h-[28rem] flex-col overflow-hidden md:min-h-[29rem] xl:min-h-[30rem]"
      tone="accent"
    >
      {heroBackgroundUrl ? (
        <>
          <Image
            alt=""
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 scale-[1.03] object-cover object-[center_100%] opacity-[0.76] saturate-[1.1] contrast-[1.03] brightness-[0.98]"
            fill
            sizes="100vw"
            src={heroBackgroundUrl}
            unoptimized
          />
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 bg-[linear-gradient(108deg,rgba(30,18,6,0.46)_0%,rgba(82,57,12,0.28)_44%,rgba(138,109,24,0.22)_100%)]"
          />
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_18%_22%,rgba(255,244,216,0.16),transparent_28%),radial-gradient(circle_at_82%_18%,rgba(243,223,159,0.16),transparent_26%),linear-gradient(180deg,rgba(16,9,2,0.02),rgba(16,9,2,0.1))]"
          />
        </>
      ) : null}

      <div className="relative z-10 flex flex-1 flex-col gap-6">
        <div className="flex flex-1 items-center">
          <div className="grid w-full gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(22rem,0.9fr)] xl:items-start">
            <div className="flex min-w-0 flex-col gap-4">
              <div className="space-y-3">
                {kicker ? (
                  <p className="text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-white/72">{kicker}</p>
                ) : null}
                <h1 className="max-w-4xl font-[family:var(--font-profile-headline)] text-[2.95rem] font-extrabold leading-[0.95] tracking-[-0.06em] text-white md:text-[3.7rem]">
                  {title}
                </h1>
              </div>

              {description || footer ? (
                <div className="space-y-4">
                  {description ? (
                    <p className="max-w-2xl text-sm/7 text-[#d7efe4] md:text-[0.98rem]/7">{description}</p>
                  ) : null}
                  {footer ? <div className="flex flex-wrap items-center gap-2">{footer}</div> : null}
                </div>
              ) : null}
            </div>

            {aside ? (
              <aside
                className={joinClasses(
                  "rounded-[1.7rem] border border-white/10 bg-white/[0.07] p-4 shadow-[0_24px_54px_-42px_rgba(2,12,9,0.55)] backdrop-blur-xl",
                  asideClassName,
                )}
              >
                {aside}
              </aside>
            ) : null}
          </div>
        </div>

        {metrics ? <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">{metrics}</div> : null}
      </div>
    </ProfilePanel>
  );
}
