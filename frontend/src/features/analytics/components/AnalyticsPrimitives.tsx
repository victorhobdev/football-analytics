"use client";

import type { ReactNode } from "react";

function joinClasses(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}
export function AnalyticsPanel({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={joinClasses(
        "rounded-xl border border-[rgba(191,201,195,0.34)] bg-white/82 p-4 shadow-[0_18px_50px_-42px_rgba(17,28,45,0.28)] backdrop-blur-xl md:p-5",
        className,
      )}
    >
      {children}
    </section>
  );
}
export function AnalyticsSectionHeader({
  eyebrow,
  title,
  description,
  aside,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  aside?: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
      <div className="min-w-0">
        {eyebrow ? (
          <p className="text-[0.68rem] font-bold uppercase tracking-[0.18em] text-[#57657a]">
            {eyebrow}
          </p>
        ) : null}
        <h2 className="mt-1 font-[family:var(--font-profile-headline)] text-2xl font-extrabold tracking-[-0.035em] text-[#111c2d]">
          {title}
        </h2>
        {description ? <p className="mt-1 max-w-3xl text-sm/6 text-[#57657a]">{description}</p> : null}
      </div>
      {aside ? <div className="flex shrink-0 flex-wrap items-center gap-2">{aside}</div> : null}
    </div>
  );
}

export function AnalyticsKpi({
  label,
  value,
  hint,
  tone = "base",
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: "base" | "accent" | "soft";
}) {
  const toneClasses =
    tone === "accent"
      ? "border-[#003526]/10 bg-[#003526] text-white shadow-[0_20px_44px_-32px_rgba(0,53,38,0.9)]"
      : tone === "soft"
        ? "border-[rgba(216,227,251,0.76)] bg-[rgba(240,243,255,0.82)] text-[#111c2d]"
        : "border-white/72 bg-white/78 text-[#111c2d]";

  return (
    <article className={joinClasses("rounded-lg border px-4 py-3", toneClasses)}>
      <p className={joinClasses("text-[0.66rem] font-bold uppercase tracking-[0.12em]", tone === "accent" ? "text-white/68" : "text-[#57657a]")}>
        {label}
      </p>
      <p className="mt-1.5 break-words font-[family:var(--font-profile-headline)] text-2xl font-extrabold leading-tight tracking-[-0.02em]">
        {value}
      </p>
      {hint ? (
        <p className={joinClasses("mt-1.5 text-xs leading-5", tone === "accent" ? "text-white/70" : "text-[#57657a]")}>
          {hint}
        </p>
      ) : null}
    </article>
  );
}

export function AnalyticsSelect({
  label,
  onChange,
  options,
  value,
}: {
  label: string;
  onChange: (value: string) => void;
  options: Array<{ label: string; value: string }>;
  value: string;
}) {
  return (
    <label className="flex min-w-[11rem] flex-1 flex-col gap-2 text-[0.66rem] font-bold uppercase tracking-[0.12em] text-[#57657a] sm:flex-none">
      {label}
      <select
        className="h-10 rounded-lg border border-[rgba(191,201,195,0.55)] bg-[#f9f9ff] px-3 text-sm font-semibold normal-case tracking-normal text-[#111c2d] outline-none shadow-[inset_0_1px_0_rgba(255,255,255,0.85)] transition-colors focus:border-[#0f513c]"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}
