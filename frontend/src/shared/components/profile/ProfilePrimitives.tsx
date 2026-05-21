import type { ReactNode } from "react";

import Link from "next/link";
import { Inter, Manrope } from "next/font/google";

import type { CoverageState, CoverageStatus } from "@/shared/types/coverage.types";

const profileBodyFont = Inter({
  subsets: ["latin"],
  variable: "--font-profile-body",
  weight: ["400", "500", "600", "700"],
});

const profileHeadlineFont = Manrope({
  subsets: ["latin"],
  variable: "--font-profile-headline",
  weight: ["700", "800"],
});

export const profileTypographyClassName = profileBodyFont.className;
export const profileHeadlineVariableClassName = profileHeadlineFont.variable;

function joinClasses(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

const PROFILE_COVERAGE_CLASSES: Record<CoverageStatus, string> = {
  complete: "bg-[#a6f2d1] text-[#00513b]",
  partial: "bg-[#ffdcc3] text-[#6e3900]",
  empty: "bg-[#ffdad6] text-[#93000a]",
  unknown: "bg-[#d8e3fb] text-[#404944]",
};

const PROFILE_ALERT_CLASSES = {
  critical: "border border-[#ffdad6] bg-[#fff1ef] text-[#93000a]",
  warning: "border border-[#ffdcc3] bg-[#fff3e8] text-[#6e3900]",
  info: "border border-[rgba(191,201,195,0.55)] bg-white/78 text-[#404944]",
} as const;

export function ProfileShell({
  children,
  className,
  contentClassName,
  variant = "surface",
}: {
  children: ReactNode;
  className?: string;
  contentClassName?: string;
  variant?: "plain" | "surface";
}) {
  const isPlain = variant === "plain";
  const Element = isPlain ? "div" : "main";

  return (
    <Element
      className={joinClasses(
        profileTypographyClassName,
        profileHeadlineVariableClassName,
        isPlain
          ? "text-[#111c2d]"
          : "relative isolate overflow-hidden rounded-[2.1rem] border border-white/60 bg-[linear-gradient(180deg,rgba(243,247,241,0.96)_0%,rgba(248,250,255,0.98)_46%,rgba(245,249,245,0.96)_100%)] p-4 text-[#111c2d] shadow-[0_36px_92px_-58px_rgba(9,25,20,0.28)] md:p-6 xl:p-8",
        className,
      )}
    >
      {!isPlain ? (
        <div className="pointer-events-none absolute inset-x-0 top-0 h-52 bg-[radial-gradient(circle_at_top_left,rgba(216,227,251,0.82),transparent_50%),radial-gradient(circle_at_top_right,rgba(139,214,182,0.28),transparent_42%)]" />
      ) : null}
      <div className={joinClasses(isPlain ? "space-y-6" : "relative z-10 space-y-6", contentClassName)}>
        {children}
      </div>
    </Element>
  );
}

export function ProfilePanel({
  children,
  className,
  tone = "base",
}: {
  children: ReactNode;
  className?: string;
  tone?: "base" | "accent" | "soft";
}) {
  const toneClasses =
    tone === "accent"
      ? "border border-white/10 bg-[radial-gradient(circle_at_top_left,rgba(41,125,96,0.34),transparent_42%),linear-gradient(135deg,#06271d_0%,#0a3d2c_54%,#0f513c_100%)] text-white shadow-[0_34px_84px_-52px_rgba(0,53,38,0.64)]"
      : tone === "soft"
        ? "border border-[rgba(216,227,251,0.7)] bg-[rgba(240,243,255,0.78)] text-[#111c2d]"
        : "border border-white/60 bg-[rgba(255,255,255,0.76)] text-[#111c2d] shadow-[0_24px_64px_-50px_rgba(17,28,45,0.22)]";

  return (
    <section
      className={joinClasses(
        "rounded-[1.75rem] p-5 backdrop-blur-xl md:p-6",
        toneClasses,
        className,
      )}
    >
      {children}
    </section>
  );
}

type ProfileTabItem = {
  badge?: ReactNode;
  href: string;
  isActive: boolean;
  key: string;
  label: ReactNode;
  customComponent?: ReactNode;
};

export function ProfileTabs({
  ariaLabel,
  items,
  aside,
  className,
  density = "default",
}: {
  ariaLabel: string;
  items: ProfileTabItem[];
  aside?: ReactNode;
  className?: string;
  density?: "compact" | "default";
}) {
  const isCompact = density === "compact";

  return (
    <ProfilePanel
      className={joinClasses(
        isCompact
          ? "flex flex-col gap-2 border border-[rgba(191,201,195,0.3)] md:flex-row md:items-center md:justify-between"
          : "flex flex-col gap-4 border border-[rgba(191,201,195,0.3)] md:flex-row md:items-center md:justify-between",
        className,
      )}
      tone="soft"
    >
      <nav aria-label={ariaLabel} className={joinClasses("flex flex-wrap items-center", isCompact ? "gap-1.5" : "gap-2")}>
        {items.map((item) => {
          if (item.customComponent) {
            return <div key={item.key}>{item.customComponent}</div>;
          }

          return (
            <Link
              aria-current={item.isActive ? "page" : undefined}
              aria-label={typeof item.label === "string" ? item.label : undefined}
              className={
                item.isActive
                  ? joinClasses(
                      "inline-flex items-center gap-2 rounded-full bg-[#003526] font-bold uppercase !text-white shadow-[0_12px_32px_-16px_rgba(0,53,38,0.7)]",
                      isCompact
                        ? "px-3 py-1.5 text-[0.68rem] tracking-[0.14em]"
                        : "px-4 py-2 text-xs tracking-[0.18em]",
                    )
                  : joinClasses(
                      "inline-flex items-center gap-2 rounded-full border border-[rgba(191,201,195,0.5)] bg-white font-semibold uppercase text-[#404944] transition-colors hover:border-[#8bd6b6] hover:bg-[#f0faf6]",
                      isCompact
                        ? "px-3 py-1.5 text-[0.68rem] tracking-[0.14em]"
                        : "px-4 py-2 text-xs tracking-[0.18em]",
                    )
              }
              href={item.href}
              key={item.key}
            >
              <span>{item.label}</span>
              {item.badge ? (
                <span
                  className={
                    item.isActive
                      ? "rounded-full bg-white/14 px-2 py-0.5 text-[0.62rem] font-semibold"
                      : "rounded-full bg-[rgba(216,227,251,0.88)] px-2 py-0.5 text-[0.62rem] font-semibold"
                  }
                >
                  {item.badge}
                </span>
              ) : null}
            </Link>
          );
        })}
      </nav>

      {aside ? <div className="flex flex-wrap items-center gap-2">{aside}</div> : null}
    </ProfilePanel>
  );
}

export function ProfileCoveragePill({
  coverage,
  className,
}: {
  coverage: CoverageState;
  className?: string;
}) {
  const label = coverage.label ?? coverage.status;
  const shouldShowPercentage =
    typeof coverage.percentage === "number" && (coverage.status === "partial" || !coverage.label);
  const percentage = shouldShowPercentage ? ` ${coverage.percentage?.toFixed(0)}%` : "";

  return (
    <span
      className={joinClasses(
        "inline-flex items-center rounded-full px-3 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.18em]",
        PROFILE_COVERAGE_CLASSES[coverage.status],
        className,
      )}
    >
      {label}
      {percentage}
    </span>
  );
}

export function ProfileTag({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={joinClasses(
        "inline-flex items-center rounded-full bg-[rgba(216,227,251,0.72)] px-3 py-1 text-[0.7rem] font-semibold uppercase tracking-[0.18em] text-[#404944]",
        className,
      )}
    >
      {children}
    </span>
  );
}

export function ProfileKpi({
  label,
  value,
  hint,
  invert = false,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  invert?: boolean;
}) {
  return (
    <article
      className={joinClasses(
        "rounded-[1.35rem] border px-4 py-4",
        invert
          ? "border-white/10 bg-white/8 text-white"
          : "border-white/72 bg-white/72 text-[#111c2d]",
      )}
    >
      <p className={joinClasses("text-[0.72rem] uppercase tracking-[0.16em]", invert ? "text-white/68" : "text-[#57657a]")}>
        {label}
      </p>
      <p className="mt-2 font-[family:var(--font-profile-headline)] text-3xl font-extrabold leading-none">
        {value}
      </p>
      {hint ? (
        <p className={joinClasses("mt-3 text-sm", invert ? "text-white/70" : "text-[#515f74]")}>
          {hint}
        </p>
      ) : null}
    </article>
  );
}

export function ProfileMetricTile({
  label,
  value,
  tone = "base",
}: {
  label: string;
  value: ReactNode;
  tone?: "base" | "soft";
}) {
  return (
    <article
      className={joinClasses(
        "rounded-[1.25rem] border px-4 py-4",
        tone === "soft"
          ? "border-[rgba(216,227,251,0.7)] bg-[rgba(240,243,255,0.76)]"
          : "border-white/70 bg-[rgba(255,255,255,0.78)]",
      )}
    >
      <p className="text-[0.72rem] uppercase tracking-[0.16em] text-[#57657a]">{label}</p>
      <p className="mt-2 font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#111c2d]">
        {value}
      </p>
    </article>
  );
}

export function ProfileAlert({
  title,
  children,
  tone = "info",
  className,
}: {
  title: string;
  children: ReactNode;
  tone?: "critical" | "warning" | "info";
  className?: string;
}) {
  return (
    <section
      className={joinClasses(
        "rounded-[1.1rem] px-4 py-3 text-sm",
        PROFILE_ALERT_CLASSES[tone],
        className,
      )}
    >
      <p className="font-semibold">{title}</p>
      <div className="mt-1 text-sm/6">{children}</div>
    </section>
  );
}
