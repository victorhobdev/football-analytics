import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const page = readFileSync("src/app/(platform)/(home)/HomeExecutivePage.tsx", "utf8");
const styles = readFileSync("src/app/(platform)/(home)/HomeExecutivePage.module.css", "utf8");

test("home hero uses the editorial message and integrated dark metrics", () => {
  const metricCard = styles.match(/\.metricCard\s*\{([\s\S]*?)\n\}/)?.[1] ?? "";

  assert.match(page, /O futebol inteiro/);
  assert.match(page, /styles\.heroLead/);
  assert.doesNotMatch(metricCard, /background:\s*rgba\(255/);
  assert.match(styles, /\.heroMetricsPanel\s*\{[\s\S]*?background:/);
});
