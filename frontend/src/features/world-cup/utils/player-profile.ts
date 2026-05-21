export function resolveWorldCupPlayerImageAssetId(
  imageAssetId: string | null | undefined,
  playerId: string | null | undefined,
): string | null {
  const normalizedImageAssetId = imageAssetId?.trim();

  return normalizedImageAssetId || playerId?.trim() || null;
}
