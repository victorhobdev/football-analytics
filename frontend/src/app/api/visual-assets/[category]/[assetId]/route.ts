import { promises as fs } from "fs";
import path from "path";

import { NextResponse, type NextRequest } from "next/server";

type ManifestEntry = {
  entity_id?: number;
  local_path?: string;
  content_type?: string;
};

type ManifestFile = {
  entries?: ManifestEntry[];
};

const ALLOWED_CATEGORIES = new Set(["clubs", "competitions", "players"]);
type CachedManifest = {
  entries: ManifestEntry[];
  mtimeMs: number;
  loadedAtMs?: number;
};

const manifestCache = new Map<string, CachedManifest>();
const REMOTE_MANIFEST_CACHE_TTL_MS = 5 * 60 * 1000;

function resolveConfiguredValue(...values: Array<string | undefined>): string | null {
  return (
    values
      .map((value) => value?.trim())
      .find((value): value is string => Boolean(value)) ?? null
  );
}

function resolveVisualAssetsRoot(): string {
  const configuredRoot = resolveConfiguredValue(
    process.env.FOOTBALL_VISUAL_ASSETS_ROOT,
    process.env.VISUAL_ASSETS_ROOT,
  );

  if (configuredRoot) {
    return path.resolve(configuredRoot);
  }

  return path.resolve(process.cwd(), "..", "data", "visual_assets");
}

function resolvePublicAssetsBaseUrl(): string | null {
  return resolveConfiguredValue(
    process.env.FOOTBALL_VISUAL_ASSETS_PUBLIC_BASE_URL,
    process.env.VISUAL_ASSETS_PUBLIC_BASE_URL,
  );
}

function resolveManifestBaseUrl(): string | null {
  return resolveConfiguredValue(
    process.env.FOOTBALL_VISUAL_ASSETS_MANIFEST_BASE_URL,
    process.env.VISUAL_ASSETS_MANIFEST_BASE_URL,
  );
}

function resolveRemoteManifestUrl(category: string): string | null {
  const baseUrl = resolveManifestBaseUrl();
  if (!baseUrl) {
    return null;
  }

  return new URL(`${category}.json`, baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`).toString();
}

function resolveManifestPath(category: string): string {
  return path.resolve(resolveVisualAssetsRoot(), "manifests", `${category}.json`);
}

function normalizeAssetRelativePath(localPath: string): string | null {
  const normalizedLocalPath = localPath.replaceAll("\\", "/");
  const legacyPrefix = "data/visual_assets/";
  const relativeAssetPath = normalizedLocalPath.startsWith(legacyPrefix)
    ? normalizedLocalPath.slice(legacyPrefix.length)
    : normalizedLocalPath;

  if (
    relativeAssetPath === "" ||
    path.isAbsolute(relativeAssetPath) ||
    relativeAssetPath.startsWith("/") ||
    relativeAssetPath.split("/").includes("..")
  ) {
    return null;
  }

  return relativeAssetPath;
}

function isPathInside(parentPath: string, candidatePath: string): boolean {
  const relativePath = path.relative(parentPath, candidatePath);
  return relativePath === "" || (!relativePath.startsWith("..") && !path.isAbsolute(relativePath));
}

function resolveAssetPath(localPath: string): string | null {
  const assetsRoot = resolveVisualAssetsRoot();
  const relativeAssetPath = normalizeAssetRelativePath(localPath);
  if (!relativeAssetPath) {
    return null;
  }

  const assetPath = path.resolve(assetsRoot, relativeAssetPath);

  return isPathInside(assetsRoot, assetPath) ? assetPath : null;
}

function resolvePublicAssetUrl(localPath: string): string | null {
  const baseUrl = resolvePublicAssetsBaseUrl();
  const relativeAssetPath = normalizeAssetRelativePath(localPath);
  if (!baseUrl || !relativeAssetPath) {
    return null;
  }

  return new URL(relativeAssetPath, baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`).toString();
}

async function fetchPublicAsset(publicAssetUrl: string, fallbackContentType?: string): Promise<NextResponse> {
  const upstreamResponse = await fetch(publicAssetUrl, {
    headers: { Accept: "image/*,*/*;q=0.8" },
    cache: "force-cache",
    next: { revalidate: 86_400 },
  });

  if (!upstreamResponse.ok) {
    return NextResponse.json(
      { message: "Asset não encontrado." },
      { status: upstreamResponse.status },
    );
  }

  const headers = new Headers();
  headers.set("Cache-Control", "public, max-age=86400, immutable");
  headers.set(
    "Content-Type",
    upstreamResponse.headers.get("Content-Type") ?? fallbackContentType ?? "image/png",
  );

  return new NextResponse(upstreamResponse.body, {
    status: upstreamResponse.status,
    headers,
  });
}

async function loadManifestEntries(category: string): Promise<ManifestEntry[]> {
  const remoteManifestUrl = resolveRemoteManifestUrl(category);
  if (remoteManifestUrl) {
    const cacheKey = `remote:${category}`;
    const cached = manifestCache.get(cacheKey);
    const now = Date.now();

    if (cached?.loadedAtMs && now - cached.loadedAtMs < REMOTE_MANIFEST_CACHE_TTL_MS) {
      return cached.entries;
    }

    const response = await fetch(remoteManifestUrl, {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      const error = new Error(`Unable to load visual asset manifest: ${remoteManifestUrl}`);
      (error as NodeJS.ErrnoException).code = response.status === 404 ? "ENOENT" : "EIO";
      throw error;
    }

    const parsedManifest = (await response.json()) as ManifestFile;
    const entries = Array.isArray(parsedManifest.entries) ? parsedManifest.entries : [];
    manifestCache.set(cacheKey, {
      entries,
      mtimeMs: now,
      loadedAtMs: now,
    });
    return entries;
  }

  const manifestPath = resolveManifestPath(category);
  const manifestStat = await fs.stat(manifestPath);
  const cacheKey = `local:${category}`;
  const cached = manifestCache.get(cacheKey);

  if (cached && cached.mtimeMs === manifestStat.mtimeMs) {
    return cached.entries;
  }

  const rawManifest = await fs.readFile(manifestPath, "utf8");
  const parsedManifest = JSON.parse(rawManifest) as ManifestFile;
  const entries = Array.isArray(parsedManifest.entries) ? parsedManifest.entries : [];

  manifestCache.set(cacheKey, {
    entries,
    mtimeMs: manifestStat.mtimeMs,
  });
  return entries;
}

export async function GET(
  _request: NextRequest,
  context: { params: Promise<{ category: string; assetId: string }> },
) {
  const { category, assetId } = await context.params;

  if (!ALLOWED_CATEGORIES.has(category) || !/^\d+$/.test(assetId)) {
    return NextResponse.json({ message: "Asset não encontrado." }, { status: 404 });
  }

  let entries: ManifestEntry[];
  try {
    entries = await loadManifestEntries(category);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") {
      return NextResponse.json({ message: "Asset não encontrado." }, { status: 404 });
    }
    throw error;
  }

  const entry = entries.find(
    (candidate) =>
      typeof candidate.entity_id === "number" &&
      String(candidate.entity_id) === assetId &&
      typeof candidate.local_path === "string",
  );

  if (!entry?.local_path) {
    return NextResponse.json({ message: "Asset não encontrado." }, { status: 404 });
  }

  const publicAssetUrl = resolvePublicAssetUrl(entry.local_path);
  if (publicAssetUrl) {
    return fetchPublicAsset(publicAssetUrl, entry.content_type);
  }

  const assetPath = resolveAssetPath(entry.local_path);
  if (!assetPath) {
    return NextResponse.json({ message: "Asset não encontrado." }, { status: 404 });
  }

  let buffer: Buffer;
  try {
    buffer = await fs.readFile(assetPath);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") {
      return NextResponse.json({ message: "Asset não encontrado." }, { status: 404 });
    }
    throw error;
  }

  return new NextResponse(new Uint8Array(buffer), {
    headers: {
      "Cache-Control": "public, max-age=86400, immutable",
      "Content-Type": entry.content_type ?? "image/png",
    },
  });
}
