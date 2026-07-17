import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const route = readFileSync("src/app/bff/[...path]/route.ts", "utf8");

test("public BFF reads use the Next cache without caching private requests", () => {
  assert.match(route, /cache: cacheable \? "force-cache" : "no-store"/);
  assert.match(route, /headers: cacheable \? \{ Accept: "application\/json" \}/);
  assert.match(route, /next: \{ revalidate: BFF_REVALIDATE_SECONDS \}/);
  assert.match(route, /: \{ signal: request\.signal \}/);
  assert.match(route, /request\.headers\.has\("authorization"\)/);
  assert.match(route, /request\.headers\.has\("cookie"\)/);
});
