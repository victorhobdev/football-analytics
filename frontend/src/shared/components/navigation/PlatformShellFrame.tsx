"use client";

import Link from "next/link";

import { usePlatformShellState } from "@/shared/components/navigation/usePlatformShellState";

function joinClasses(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

export function PlatformShellFrame({
  compact = false,
  contentWidthClassName = "max-w-7xl",
}: {
  compact?: boolean;
  contentWidthClassName?: string;
}) {
  const shellState = usePlatformShellState();

  return (
    <section
      aria-label="Contexto da página"
      className="border-b border-[rgba(216,227,251,0.72)] bg-[linear-gradient(180deg,rgba(255,255,255,0.88)_0%,rgba(246,249,255,0.84)_100%)] shadow-[0_14px_34px_-34px_rgba(17,28,45,0.18)] backdrop-blur-xl"
    >
      <div
        className={joinClasses(
          "mx-auto w-full px-4 md:px-8",
          compact ? "py-2" : "py-4",
          contentWidthClassName,
        )}
      >
        <div className={joinClasses("flex flex-col", compact ? "gap-2" : "gap-4")}>
          <div className="flex flex-wrap items-center gap-2 text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-[#57657a]">
            {shellState.breadcrumbs.map((breadcrumb, index) => (
              <span className="inline-flex items-center gap-2" key={`${breadcrumb.label}-${index}`}>
                {index > 0 ? <span className="text-[#8fa097]">/</span> : null}
                {breadcrumb.href ? (
                  <Link className="transition-colors hover:text-[#003526]" href={breadcrumb.href}>
                    {breadcrumb.label}
                  </Link>
                ) : (
                  <span>{breadcrumb.label}</span>
                )}
              </span>
            ))}
          </div>

          {shellState.surfaceLinks.length > 0 ? (
            <nav aria-label="Atalhos da página" className="flex flex-wrap items-center gap-2">
              {shellState.surfaceLinks.map((link) => (
                <Link
                  className={joinClasses(
                    "inline-flex items-center rounded-full px-4 py-2 text-[0.72rem] font-bold uppercase tracking-[0.16em] transition-[transform,background-color,color] duration-200 ease-[cubic-bezier(0.23,1,0.32,1)] active:scale-[0.985]",
                    link.isActive
                      ? "bg-[#003526] !text-white shadow-[0_12px_32px_-16px_rgba(0,53,38,0.7)]"
                      : "bg-[rgba(240,243,255,0.96)] text-[#1f2d40] hover:-translate-y-0.5 hover:bg-white border border-[rgba(191,201,195,0.5)]",
                  )}
                  href={link.href}
                  key={link.href}
                >
                  {link.label}
                </Link>
              ))}
            </nav>
          ) : null}
        </div>
      </div>
    </section>
  );
}
