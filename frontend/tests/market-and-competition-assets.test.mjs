import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const marketSource = readFileSync("src/features/market/components/MarketPageContent.tsx", "utf8");
const competitionsSource = readFileSync("src/app/(platform)/competitions/page.tsx", "utf8");

test("Mercado starts sorted by transfer amount", () => {
  assert.match(marketSource, /useState<[^>]+>\("amountDesc"\)/);
});

test("unregistered competitions resolve assets by their manifest key", () => {
  assert.match(competitionsSource, /card\.competitionKey \?\? card\.assetId \?\? card\.competitionId/);
});
