import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

type Scope = "mundial" | "continental" | "nacional" | "estadual";

type CsvRow = {
  team_slug: string;
  team_name: string;
  scope: string;
  competition_name: string;
  competition_family: string;
  year: string;
  season_label: string;
  title_type: string;
  source_name: string;
  source_url: string;
  confidence: string;
  notes: string;
};

type ScopeItem = {
  label: string;
  count: number;
};

type ScopeBlock = {
  scope: Scope;
  label: string;
  total: number;
  items: ScopeItem[];
};

type PreviewPayload = {
  teamSlug: string;
  teamName: string;
  criterionLabel: string;
  scopes: ScopeBlock[];
};

const CSV_PATH = path.resolve("data", "team_honors_seed.csv");
const OUTPUT_DIR = path.resolve("data", "team_honors_preview");
const SCOPE_ORDER: Scope[] = ["mundial", "continental", "nacional", "estadual"];
const SCOPE_LABEL: Record<Scope, string> = {
  mundial: "Mundial",
  continental: "Continental",
  nacional: "Nacional",
  estadual: "Estadual",
};
const COMPETITION_LABEL_MAP: Record<string, string> = {
  mundial_clubes: "Mundial",
  libertadores: "Copa Libertadores",
  brasileirao_serie_a: "Campeonato Brasileiro",
  copa_do_brasil: "Copa do Brasil",
  campeonato_carioca: "Campeonato Carioca",
};

function splitCsvLine(line: string): string[] {
  const values: string[] = [];
  let current = "";
  let inQuotes = false;

  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];

    if (char === '"') {
      const nextChar = line[i + 1];
      if (inQuotes && nextChar === '"') {
        current += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (char === "," && !inQuotes) {
      values.push(current);
      current = "";
      continue;
    }

    current += char;
  }

  values.push(current);
  return values.map((value) => value.trim());
}

function parseCsv(fileContent: string): CsvRow[] {
  const lines = fileContent
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  if (lines.length < 2) {
    return [];
  }

  const header = splitCsvLine(lines[0]);
  const rows: CsvRow[] = [];

  for (let lineIndex = 1; lineIndex < lines.length; lineIndex += 1) {
    const values = splitCsvLine(lines[lineIndex]);
    if (values.length !== header.length) {
      console.warn(
        `[warning] Linha ${lineIndex + 1}: colunas esperadas=${header.length}, recebidas=${values.length}.`
      );
      continue;
    }

    const rowObject = Object.fromEntries(
      header.map((columnName, index) => [columnName, values[index] ?? ""])
    ) as CsvRow;
    rows.push(rowObject);
  }

  return rows;
}

function titleCaseFromSlug(raw: string): string {
  return raw
    .split(/[_-]+/)
    .filter(Boolean)
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join(" ");
}

function assertTeamSlugArg(): string {
  const teamSlugArg = process.argv[2]?.trim();
  if (!teamSlugArg) {
    console.error("Uso: node platform/scripts/preview-team-honors.ts <team_slug>");
    process.exit(1);
  }
  return teamSlugArg;
}

function main(): void {
  const teamSlug = assertTeamSlugArg();
  const csvContent = readFileSync(CSV_PATH, "utf-8");
  const rows = parseCsv(csvContent);

  if (rows.length === 0) {
    console.error("Nenhuma linha válida encontrada no CSV.");
    process.exit(1);
  }

  const rowsForTeam = rows.filter((row) => row.team_slug === teamSlug);
  if (rowsForTeam.length === 0) {
    console.error(`Nenhuma linha encontrada para team_slug="${teamSlug}".`);
    process.exit(1);
  }

  const duplicateKeyMap = new Map<string, number[]>();
  rowsForTeam.forEach((row, idx) => {
    const duplicateKey = [
      row.team_slug,
      row.competition_family,
      row.season_label,
      row.title_type,
    ].join("|");
    const lineNumbers = duplicateKeyMap.get(duplicateKey) ?? [];
    lineNumbers.push(idx + 2);
    duplicateKeyMap.set(duplicateKey, lineNumbers);
  });

  for (const [key, lineNumbers] of duplicateKeyMap.entries()) {
    if (lineNumbers.length > 1) {
      console.warn(
        `[warning] Duplicata provável (${key}) nas linhas ${lineNumbers.join(", ")}.`
      );
    }
  }

  const championRows = rowsForTeam.filter((row) => row.title_type === "champion");
  const teamName = championRows[0]?.team_name ?? rowsForTeam[0]?.team_name ?? "";

  const perScope = new Map<Scope, Map<string, number>>();
  const displayLabelByFamily = new Map<string, string>();

  for (const row of championRows) {
    const scope = row.scope as Scope;
    if (!SCOPE_ORDER.includes(scope)) {
      console.warn(
        `[warning] Scope inválido para ${teamSlug}: "${row.scope}" (${row.competition_name}, ${row.season_label}).`
      );
      continue;
    }

    const byFamily = perScope.get(scope) ?? new Map<string, number>();
    byFamily.set(
      row.competition_family,
      (byFamily.get(row.competition_family) ?? 0) + 1
    );
    perScope.set(scope, byFamily);

    if (!displayLabelByFamily.has(row.competition_family)) {
      displayLabelByFamily.set(row.competition_family, row.competition_name);
    }
  }

  const scopes: ScopeBlock[] = [];

  for (const scope of SCOPE_ORDER) {
    const byFamily = perScope.get(scope);
    if (!byFamily || byFamily.size === 0) {
      continue;
    }

    const items: ScopeItem[] = Array.from(byFamily.entries())
      .sort((a, b) => a[0].localeCompare(b[0], "pt-BR"))
      .map(([competitionFamily, count]) => {
        const label =
          COMPETITION_LABEL_MAP[competitionFamily] ??
          displayLabelByFamily.get(competitionFamily) ??
          titleCaseFromSlug(competitionFamily);
        return { label, count };
      });

    const total = items.reduce((acc, item) => acc + item.count, 0);

    scopes.push({
      scope,
      label: SCOPE_LABEL[scope],
      total,
      items,
    });
  }

  const payload: PreviewPayload = {
    teamSlug,
    teamName,
    criterionLabel: "Títulos oficiais selecionados para o acervo histórico.",
    scopes,
  };

  mkdirSync(OUTPUT_DIR, { recursive: true });
  const outputPath = path.join(OUTPUT_DIR, `${teamSlug}.json`);
  const jsonOutput = JSON.stringify(payload, null, 2);
  writeFileSync(outputPath, jsonOutput, "utf-8");

  console.log(jsonOutput);
}

main();
