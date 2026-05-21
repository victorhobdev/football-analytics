import { promises as fs } from "fs";
import path from "path";

import { NextResponse, type NextRequest } from "next/server";

type ManifestEntry = {
  entity_id?: number | string;
  entity_key?: string;
  local_path?: string;
  content_type?: string;
};

type ManifestFile = {
  entries?: ManifestEntry[];
};

const ALLOWED_CATEGORIES = new Set(["clubs", "coaches", "competitions", "countries", "players"]);
const ASSET_ID_PATTERN = /^[A-Za-z0-9_-]+$/;
type CachedManifest = {
  entries: ManifestEntry[];
  mtimeMs: number;
  loadedAtMs?: number;
};

const manifestCache = new Map<string, CachedManifest>();
const manifestEntryIndexCache = new WeakMap<ManifestEntry[], Map<string, ManifestEntry>>();
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

function resolveRemoteManifestUrl(fileName: string): string | null {
  const baseUrl = resolveManifestBaseUrl();
  if (!baseUrl) {
    return null;
  }

  return new URL(fileName, baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`).toString();
}

function resolveManifestPath(fileName: string): string {
  return path.resolve(resolveVisualAssetsRoot(), "manifests", fileName);
}

function buildManifestFileNames(category: string): string[] {
  const fileNames = [`${category}.json`];
  if (category !== "countries") {
    fileNames.push(`${category}.overrides.json`);
  }
  return fileNames;
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

async function loadRemoteManifestEntries(
  fileName: string,
  optional = false,
): Promise<ManifestEntry[]> {
  const remoteManifestUrl = resolveRemoteManifestUrl(fileName);
  if (!remoteManifestUrl) {
    return [];
  }

  const cacheKey = `remote:${fileName}`;
  const cached = manifestCache.get(cacheKey);
  const now = Date.now();

  if (cached?.loadedAtMs && now - cached.loadedAtMs < REMOTE_MANIFEST_CACHE_TTL_MS) {
    return cached.entries;
  }

  const response = await fetch(remoteManifestUrl, {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    if (optional && response.status === 404) {
      manifestCache.set(cacheKey, {
        entries: [],
        mtimeMs: now,
        loadedAtMs: now,
      });
      return [];
    }

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

async function loadLocalManifestEntries(
  fileName: string,
  optional = false,
): Promise<ManifestEntry[]> {
  const manifestPath = resolveManifestPath(fileName);
  let manifestStat: Awaited<ReturnType<typeof fs.stat>>;
  try {
    manifestStat = await fs.stat(manifestPath);
  } catch (error) {
    if (optional && (error as NodeJS.ErrnoException).code === "ENOENT") {
      return [];
    }
    throw error;
  }

  const cacheKey = `local:${fileName}`;
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

async function loadManifestEntries(category: string): Promise<ManifestEntry[]> {
  const manifestFileNames = buildManifestFileNames(category);
  const manifestBaseUrl = resolveManifestBaseUrl();
  const entries: ManifestEntry[] = [];

  for (const [index, fileName] of manifestFileNames.entries()) {
    const optional = index > 0;
    const manifestEntries = manifestBaseUrl
      ? await loadRemoteManifestEntries(fileName, optional)
      : await loadLocalManifestEntries(fileName, optional);
    entries.push(...manifestEntries);
  }

  return entries;
}

function findManifestEntry(entries: ManifestEntry[], assetId: string): ManifestEntry | null {
  let entryIndex = manifestEntryIndexCache.get(entries);
  if (!entryIndex) {
    entryIndex = new Map<string, ManifestEntry>();
    for (const entry of entries) {
      if (typeof entry.local_path !== "string") {
        continue;
      }

      if (typeof entry.entity_key === "string" && entry.entity_key.trim() !== "") {
        entryIndex.set(entry.entity_key.trim(), entry);
      }

      if (typeof entry.entity_id === "number" || typeof entry.entity_id === "string") {
        const entityId = String(entry.entity_id).trim();
        if (entityId !== "") {
          entryIndex.set(entityId, entry);
        }
      }
    }
    manifestEntryIndexCache.set(entries, entryIndex);
  }

  return entryIndex.get(assetId) ?? null;
}

function buildOverlayRelativePath(category: string, assetId: string): string {
  return `data/visual_assets/wc_overlay/${category}/${assetId}.png`;
}

function isOverlayLocalPath(localPath: string): boolean {
  const normalizedLocalPath = localPath.replaceAll("\\", "/");
  return normalizedLocalPath.startsWith("data/visual_assets/wc_overlay/");
}

async function resolveOverlayEntry(category: string, assetId: string): Promise<ManifestEntry | null> {
  const localPath = buildOverlayRelativePath(category, assetId);
  const assetPath = resolveAssetPath(localPath);

  if (!assetPath) {
    return null;
  }

  try {
    await fs.access(assetPath);
    return {
      entity_key: assetId,
      local_path: localPath,
      content_type: "image/png",
    };
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") {
      return null;
    }
    throw error;
  }
}

export async function GET(
  _request: NextRequest,
  context: { params: Promise<{ category: string; assetId: string }> },
) {
  const { category, assetId } = await context.params;

  if (!ALLOWED_CATEGORIES.has(category) || !ASSET_ID_PATTERN.test(assetId)) {
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

  const entry = findManifestEntry(entries, assetId) ?? (await resolveOverlayEntry(category, assetId));

  if (!entry?.local_path) {
    return NextResponse.json({ message: "Asset não encontrado." }, { status: 404 });
  }

  const publicAssetUrl = isOverlayLocalPath(entry.local_path)
    ? null
    : resolvePublicAssetUrl(entry.local_path);
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
