"use client";

import { useEffect, useMemo, useState } from "react";

import Image from "next/image";
import Link from "next/link";

import { SUPPORTED_COMPETITIONS } from "@/config/competitions.registry";

type VisualAssetCategory = "clubs" | "competitions" | "players";
type ProfileMediaLinkBehavior = "auto" | "none";

type ProfileMediaProps = {
  alt: string;
  assetId: number | string | null | undefined;
  category: VisualAssetCategory;
  fallback: string;
  className?: string;
  fallbackClassName?: string;
  href?: string | null;
  imageClassName?: string;
  linkBehavior?: ProfileMediaLinkBehavior;
  shape?: "rounded" | "circle";
  tone?: "base" | "contrast";
};

function joinClasses(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

function appendRetryQueryParam(url: string, attempt: number): string {
  if (attempt <= 0) {
    return url;
  }

  return `${url}${url.includes("?") ? "&" : "?"}retry=${attempt}`;
}

function encodePathSegment(value: string): string {
  return encodeURIComponent(value.trim());
}

function buildCompetitionProfileHref(assetId: string): string {
  const competition = SUPPORTED_COMPETITIONS.find(
    (item) => item.key === assetId || item.id === assetId || item.visualAssetId === assetId,
  );
  const competitionKey = competition?.key ?? assetId;

  if (competitionKey === "fifa_world_cup_mens") {
    return "/copa-do-mundo";
  }

  return `/competitions/${encodePathSegment(competitionKey)}`;
}

function buildDefaultProfileMediaHref(
  category: VisualAssetCategory,
  assetId: number | string | null | undefined,
): string | null {
  if (assetId === null || assetId === undefined) {
    return null;
  }

  const normalizedAssetId = String(assetId).trim();

  if (normalizedAssetId.length === 0) {
    return null;
  }

  if (category === "players") {
    return `/players/${encodePathSegment(normalizedAssetId)}`;
  }

  if (category === "clubs") {
    if (normalizedAssetId.startsWith("world-cup-")) {
      return `/copa-do-mundo/selecoes/${encodePathSegment(normalizedAssetId)}`;
    }

    return `/teams/${encodePathSegment(normalizedAssetId)}`;
  }

  return buildCompetitionProfileHref(normalizedAssetId);
}

export function buildVisualAssetUrl(
  category: VisualAssetCategory,
  assetId: number | string | null | undefined,
): string | null {
  if (assetId === null || assetId === undefined) {
    return null;
  }

  const normalizedAssetId = String(assetId).trim();

  if (normalizedAssetId.length === 0) {
    return null;
  }

  return `/api/visual-assets/${category}/${normalizedAssetId}`;
}

export function ProfileMedia({
  alt,
  assetId,
  category,
  fallback,
  className,
  fallbackClassName,
  href,
  imageClassName,
  linkBehavior = "auto",
  shape = "rounded",
  tone = "base",
}: ProfileMediaProps) {
  const [hasError, setHasError] = useState(false);
  const [retryAttempt, setRetryAttempt] = useState(0);
  const assetUrl = buildVisualAssetUrl(category, assetId);
  const isPlayerAvatar = category === "players";
  const resolvedAssetUrl = useMemo(
    () => (assetUrl ? appendRetryQueryParam(assetUrl, retryAttempt) : null),
    [assetUrl, retryAttempt],
  );
  const resolvedHref = linkBehavior === "none"
    ? null
    : href !== undefined
      ? href
      : buildDefaultProfileMediaHref(category, assetId);

  useEffect(() => {
    setHasError(false);
    setRetryAttempt(0);
  }, [assetUrl]);

  const handleError = () => {
    if (!assetUrl) {
      setHasError(true);
      return;
    }

    if (retryAttempt === 0) {
      setRetryAttempt(1);
      return;
    }

    setHasError(true);
  };

  const mediaNode = (
    <div
      className={joinClasses(
        "relative flex shrink-0 items-center justify-center overflow-hidden",
        shape === "circle" ? "rounded-full" : "rounded-[1.2rem]",
        tone === "contrast"
          ? "border border-white/12 bg-white/12 text-white"
          : "border border-white/60 bg-[rgba(240,243,255,0.9)] text-[#003526]",
        className,
      )}
    >
      {resolvedAssetUrl && !hasError ? (
        <Image
          alt={alt}
          className={
            isPlayerAvatar
              ? "object-cover object-[center_20%] !p-0"
              : joinClasses("object-contain p-2", imageClassName)
          }
          fill
          key={resolvedAssetUrl}
          onError={handleError}
          sizes="96px"
          src={resolvedAssetUrl}
          unoptimized
        />
      ) : (
        <span
          className={joinClasses(
            "px-2 text-center font-[family:var(--font-app-headline)] text-xs font-extrabold uppercase tracking-[0.12em]",
            fallbackClassName,
          )}
        >
          {fallback}
        </span>
      )}
    </div>
  );

  if (!resolvedHref) {
    return mediaNode;
  }

  return (
    <Link
      aria-label={alt ? `Abrir ${alt}` : undefined}
      className="inline-flex shrink-0 rounded-[inherit] transition-opacity hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0b7f5f]"
      href={resolvedHref}
    >
      {mediaNode}
    </Link>
  );
}
