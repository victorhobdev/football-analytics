import codecs
import re

FILE_PATH = "src/app/(platform)/competitions/[competitionKey]/seasons/[seasonLabel]/CompetitionSeasonSurface.tsx"

with codecs.open(FILE_PATH, "r", "utf-8") as f:
    content = f.read()

# 1. Update Imports
content = content.replace(
    'import { useMemo, type ReactNode } from "react";',
    'import { useMemo, useState, type ReactNode } from "react";'
)
content = content.replace(
    'import { useSearchParams } from "next/navigation";',
    'import { useRouter, useSearchParams } from "next/navigation";'
)
content = content.replace(
    'import { getCompetitionByKey } from "@/config/competitions.registry";',
    'import { getCompetitionByKey, getCompetitionById, getCompetitionVisualAssetId } from "@/config/competitions.registry";'
)

# 2. Add Helper Components above `function useSeasonFilterInput`
UTILITY_COMPONENTS = """function TeamBadge({
  size = 28,
  teamId,
  teamName,
}: {
  size?: number;
  teamId?: string | null;
  teamName: string;
}) {
  const src = teamId ? `/api/visual-assets/clubs/${encodeURIComponent(teamId)}` : null;
  const initials = teamName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((t) => t[0]?.toUpperCase() ?? "")
    .join("");

  return (
    <span
      className="relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full border border-[rgba(191,201,195,0.4)] bg-[#f0f3ff]"
      style={{ width: size, height: size }}
    >
      <span className="text-[0.55rem] font-bold text-[#003526]">{initials}</span>
      {src ? (
        <img
          alt={teamName}
          className="absolute inset-0 h-full w-full object-contain bg-[#f0f3ff]"
          onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
          src={src}
        />
      ) : null}
    </span>
  );
}

function PlayerPhoto({
  playerId,
  playerName,
  size = 72,
}: {
  playerId?: string | null;
  playerName: string;
  size?: number;
}) {
  const src = playerId ? `/api/visual-assets/players/${encodeURIComponent(playerId)}` : null;
  const initials = playerName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((t) => t[0]?.toUpperCase() ?? "")
    .join("");

  return (
    <span
      className="relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full border-2 border-emerald-400/30 bg-[#003526]"
      style={{ width: size, height: size }}
    >
      <span className="text-sm font-bold text-white/70">{initials}</span>
      {src ? (
        <img
          alt={playerName}
          className="absolute inset-0 h-full w-full object-cover bg-[#003526]"
          onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
          src={src}
        />
      ) : null}
    </span>
  );
}

function CupHeroBanner({
  context,
  tag,
}: {
  context: CompetitionSeasonContext;
  tag: string;
}) {
  const compDef = getCompetitionById(context.competitionId);
  const visualAssetId = getCompetitionVisualAssetId(compDef);
  const logoSrc = visualAssetId
    ? `/api/visual-assets/competitions/${encodeURIComponent(visualAssetId)}`
    : null;
  const initials = context.competitionName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((t) => t[0]?.toUpperCase() ?? "")
    .join("");

  return (
    <div className="relative h-56 overflow-hidden rounded-xl bg-[#022e21] md:h-64">
      <div className="absolute inset-0 bg-gradient-to-r from-[#011a13] via-[#022e21]/80 to-transparent" />
      <div className="absolute -right-12 -top-12 h-64 w-64 rounded-full bg-emerald-400/10 blur-3xl" />
      <div className="absolute bottom-0 left-1/3 h-48 w-48 rounded-full bg-emerald-600/10 blur-3xl" />

      <div className="relative z-10 flex h-full items-center gap-8 px-8 md:px-10">
        <div className="relative flex h-24 w-24 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-[rgba(191,201,195,0.55)] bg-white shadow-2xl md:h-28 md:w-28">
          <span className="font-[family:var(--font-profile-headline)] text-3xl font-extrabold text-[#003526]">
            {initials || "FA"}
          </span>
          {logoSrc ? (
            <img
              alt={`Logo ${context.competitionName}`}
              className="absolute inset-0 h-full w-full object-contain bg-white p-3"
              onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
              src={logoSrc}
            />
          ) : null}
        </div>
        <div>
          <ProfileTag tone="inverse">{tag}</ProfileTag>
          <h1 className="mt-3 font-[family:var(--font-profile-headline)] text-3xl font-black tracking-[-0.03em] text-white drop-shadow-sm md:text-5xl">
            {context.competitionName}
          </h1>
          <p className="mt-2 text-base font-semibold text-white/80 drop-shadow-sm">
            {context.seasonLabel}
          </p>
        </div>
      </div>
    </div>
  );
}

function LeaguePageHeader({
  context,
  tag,
}: {
  context: CompetitionSeasonContext;
  tag: string;
}) {
  const compDef = getCompetitionById(context.competitionId);
  const visualAssetId = getCompetitionVisualAssetId(compDef);
  const logoSrc = visualAssetId
    ? `/api/visual-assets/competitions/${encodeURIComponent(visualAssetId)}`
    : null;
  const initials = context.competitionName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((t) => t[0]?.toUpperCase() ?? "")
    .join("");

  return (
    <div className="flex items-end gap-6 px-4 md:px-8 pt-8 pb-4">
      <div className="relative flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-[rgba(191,201,195,0.55)] bg-white shadow-sm md:h-20 md:w-20">
        <span className="font-[family:var(--font-profile-headline)] text-2xl font-extrabold text-[#003526]">
          {initials || "FA"}
        </span>
        {logoSrc ? (
          <img
            alt={`Logo ${context.competitionName}`}
            className="absolute inset-0 h-full w-full object-contain bg-white p-2"
            onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
            src={logoSrc}
          />
        ) : null}
      </div>
      <div>
        <div className="mb-2">
          <ProfileTag tone="soft">{tag}</ProfileTag>
        </div>
        <h1 className="font-[family:var(--font-profile-headline)] text-3xl font-black tracking-[-0.03em] text-[#111c2d]">
          {context.competitionName} {context.seasonLabel}
        </h1>
      </div>
    </div>
  );
}

function RoundPickerDropdown({ rounds, selectedRoundId, onRoundChange }: { rounds: { roundId: string; roundName: string; stageId: string }[]; selectedRoundId: string | null; onRoundChange: (id: string | null) => void; }) {
  const [isOpen, setIsOpen] = useState(false);
  const currentRound = rounds.find(r => r.roundId === selectedRoundId);

  return (
    <div className="relative w-48 z-40">
       <button onClick={() => setIsOpen(!isOpen)} className="flex items-center justify-between w-full h-10 px-4 py-2 border border-[#dcdcdc] rounded-xl text-sm font-semibold text-[#111c2d] bg-white hover:bg-[#f9fafb] transition-colors focus:ring-2 focus:ring-[#003526]/20">
           <div className="flex items-center gap-2">
               <span className="material-symbols-outlined text-[1.1rem] text-[#57657a]">calendar_month</span>
               <span>{currentRound ? currentRound.roundName : "Rodada atual"}</span>
           </div>
           <span className="material-symbols-outlined text-[1.1rem] text-[#8fa097]">unfold_more</span>
       </button>
       {isOpen && (
           <div className="absolute top-12 left-0 w-full max-h-64 overflow-y-auto bg-white border border-[#dcdcdc] rounded-xl shadow-[0_12px_24px_-12px_rgba(0,0,0,0.15)] py-2">
               {rounds.map(round => (
                   <button key={round.roundId} onClick={() => { onRoundChange(round.roundId); setIsOpen(false); }} className={`w-full text-left px-4 py-2 text-sm transition-colors hover:bg-[#f0f3ff] ${selectedRoundId === round.roundId ? "bg-[#f0f3ff] font-bold text-[#003526]" : "font-medium text-[#455468]"}`}>
                       {round.roundName}
                   </button>
               ))}
           </div>
       )}
    </div>
  );
}

"""

content = content.replace("function useSeasonFilterInput(", UTILITY_COMPONENTS + "function useSeasonFilterInput(")

# 3. Modify Nav Labels to Include the Route Cards/Rounds injection mapping.
# No need, we will directly inject `customComponent` into `navItems` array in `LeagueSeasonSurface`.

# 4. Modify LeagueSeasonSurface
LEAGUE_SEASON_SURFACE_NEW = """function LeagueSeasonSurface({
  activeSection,
  context,
  resolution,
}: {
  activeSection: CompetitionSeasonSurfaceSection;
  context: CompetitionSeasonContext;
  resolution: CompetitionSeasonSurfaceResolution;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const filterInput = useSeasonFilterInput(context);
  const navLabels = buildSurfaceNavLabels(resolution.type);

  const { setRoundId, roundId: activeRoundId } = useGlobalFiltersState();
  const standingsQuery = useStandingsTable({
    competitionId: context.competitionId,
    seasonId: context.seasonId,
    stageId: resolution.primaryTableStage?.stageId,
    roundId: activeRoundId,
  });

  const selectedRound = standingsQuery.data?.selectedRound;
  const rounds = standingsQuery.data?.rounds ?? [];

  return (
    <CompetitionSeasonSurfaceShell
      context={context}
      hero={<LeaguePageHeader context={context} tag="Pontos Corridos" />}
      navItems={[
        {
          href: buildSeasonSurfaceHref(context, "overview", searchParams),
          isActive: activeSection === "overview",
          key: "overview",
          label: navLabels.overview,
        },
        {
          href: buildSeasonSurfaceHref(context, "structure", searchParams),
          isActive: activeSection === "structure",
          key: "structure",
          label: navLabels.structure,
          customComponent: (
            <RoundPickerDropdown
              onRoundChange={(newId) => {
                setRoundId(newId);
                router.push(buildSeasonSurfaceHref(context, "structure", searchParams));
              }}
              rounds={rounds}
              selectedRoundId={selectedRound?.roundId ?? null}
            />
          ),
        },
        {
          href: buildSeasonSurfaceHref(context, "matches", searchParams),
          isActive: activeSection === "matches",
          key: "matches",
          label: navLabels.matches,
        },
        {
          href: buildSeasonSurfaceHref(context, "highlights", searchParams),
          isActive: activeSection === "highlights",
          key: "highlights",
          label: "Destaques da edicao",
        },
      ]}
      mainCanvas={
        <>
          {activeSection === "overview" ? <LeagueOverviewSection context={context} /> : null}
          {activeSection === "structure" ? <LeagueStructureSection context={context} /> : null}
          {activeSection === "matches" ? (
            <ClosingMatchesPanel
              context={context}
              description="Lista editorial das partidas de fechamento da edicao, sem tratar a liga como feed ao vivo."
              title="Partidas marcantes da temporada"
            />
          ) : null}
          {activeSection === "highlights" ? <EditionHighlightsSection context={context} structure={null} /> : null}
        </>
      }
    />
  );
}"""
content = re.sub(
    r"function LeagueSeasonSurface\(\{[\s\S]*?\}\n\s*\);\n\}",
    LEAGUE_SEASON_SURFACE_NEW,
    content,
    flags=re.MULTILINE
)

# 4. Modify CupSeasonSurface
CUP_SEASON_SURFACE_NEW = """function CupSeasonSurface({
  activeSection,
  context,
  resolution,
  structure,
}: {
  activeSection: CompetitionSeasonSurfaceSection;
  context: CompetitionSeasonContext;
  resolution: CompetitionSeasonSurfaceResolution;
  structure: CompetitionStructureData | null;
}) {
  const searchParams = useSearchParams();
  const filterInput = useSeasonFilterInput(context);
  const championTieQuery = useStageTies({
    competitionKey: context.competitionKey,
    seasonLabel: context.seasonLabel,
    stageId: resolution.finalKnockoutStage?.stageId,
  });
  const navLabels = buildSurfaceNavLabels(resolution.type);

  return (
    <CompetitionSeasonSurfaceShell
      context={context}
      hero={<CupHeroBanner tag="Mata-Mata / Eliminatorias" context={context} />}
      navItems={[
        {
          href: buildSeasonSurfaceHref(context, "overview", searchParams),
          isActive: activeSection === "overview",
          key: "overview",
          label: navLabels.overview,
        },
        {
          href: buildSeasonSurfaceHref(context, "structure", searchParams),
          isActive: activeSection === "structure",
          key: "structure",
          label: navLabels.structure,
        },
        {
          href: buildSeasonSurfaceHref(context, "matches", searchParams),
          isActive: activeSection === "matches",
          key: "matches",
          label: navLabels.matches,
        },
        {
          href: buildSeasonSurfaceHref(context, "highlights", searchParams),
          isActive: activeSection === "highlights",
          key: "highlights",
          label: "Destaques da edicao",
        },
      ]}
      mainCanvas={
        <>
          {activeSection === "overview" ? (
            <CupOverviewSection championTieQuery={championTieQuery} context={context} resolution={resolution} />
          ) : null}
          {activeSection === "structure" ? <CupStructureSection context={context} resolution={resolution} /> : null}
          {activeSection === "matches" ? (
            <KnockoutBracketPanel
              context={context}
              resolution={resolution}
            />
          ) : null}
          {activeSection === "highlights" ? <EditionHighlightsSection context={context} structure={structure} /> : null}
        </>
      }
    />
  );
}"""
content = re.sub(
    r"function CupSeasonSurface\(\{[\s\S]*?\}\n\s*\);\n\}",
    CUP_SEASON_SURFACE_NEW,
    content,
    flags=re.MULTILINE
)

# 5. Modify HybridSeasonSurface
HYBRID_SEASON_SURFACE_NEW = """function HybridSeasonSurface({
  activeSection,
  context,
  resolution,
  structure,
}: {
  activeSection: CompetitionSeasonSurfaceSection;
  context: CompetitionSeasonContext;
  resolution: CompetitionSeasonSurfaceResolution;
  structure: CompetitionStructureData | null;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const filterInput = useSeasonFilterInput(context);
  const championTieQuery = useStageTies({
    competitionKey: context.competitionKey,
    seasonLabel: context.seasonLabel,
    stageId: resolution.finalKnockoutStage?.stageId,
  });
  const navLabels = buildSurfaceNavLabels(resolution.type);

  const { setRoundId, roundId: activeRoundId } = useGlobalFiltersState();
  const standingsQuery = useStandingsTable({
    competitionId: context.competitionId,
    seasonId: context.seasonId,
    stageId: resolution.primaryTableStage?.stageId,
    roundId: activeRoundId,
  });

  const selectedRound = standingsQuery.data?.selectedRound;
  const rounds = standingsQuery.data?.rounds ?? [];

  return (
    <CompetitionSeasonSurfaceShell
      context={context}
      hero={<LeaguePageHeader context={context} tag="Formato Misto" />}
      navItems={[
        {
          href: buildSeasonSurfaceHref(context, "overview", searchParams),
          isActive: activeSection === "overview",
          key: "overview",
          label: navLabels.overview,
        },
        {
          href: buildSeasonSurfaceHref(context, "structure", searchParams),
          isActive: activeSection === "structure",
          key: "structure",
          label: navLabels.structure,
          customComponent: (
            <RoundPickerDropdown
              onRoundChange={(newId) => {
                setRoundId(newId);
                router.push(buildSeasonSurfaceHref(context, "structure", searchParams));
              }}
              rounds={rounds}
              selectedRoundId={selectedRound?.roundId ?? null}
            />
          ),
        },
        {
          href: buildSeasonSurfaceHref(context, "matches", searchParams),
          isActive: activeSection === "matches",
          key: "matches",
          label: navLabels.matches,
        },
        {
          href: buildSeasonSurfaceHref(context, "highlights", searchParams),
          isActive: activeSection === "highlights",
          key: "highlights",
          label: "Destaques da edicao",
        },
      ]}
      mainCanvas={
        <>
          {activeSection === "overview" ? <HybridOverviewSection context={context} resolution={resolution} /> : null}
          {activeSection === "structure" ? <GroupPhaseSummaryPanel context={context} stage={resolution.primaryTableStage} /> : null}
          {activeSection === "matches" ? (
            <KnockoutBracketPanel
              context={context}
              resolution={resolution}
            />
          ) : null}
          {activeSection === "highlights" ? <EditionHighlightsSection context={context} structure={structure} /> : null}
        </>
      }
    />
  );
}"""
content = re.sub(
    r"function HybridSeasonSurface\(\{[\s\S]*?\}\n\s*\);\n\}",
    HYBRID_SEASON_SURFACE_NEW,
    content,
    flags=re.MULTILINE
)

with codecs.open(FILE_PATH, "w", "utf-8") as f:
    f.write(content)
