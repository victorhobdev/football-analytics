import codecs
import re

FILE_PATH = r"c:\Users\Vitinho\Desktop\Projetos\football-analytics\frontend\src\app\(platform)\competitions\[competitionKey]\seasons\[seasonLabel]\CompetitionSeasonSurface.tsx"

with codecs.open(FILE_PATH, "r", "utf-8") as f:
    content = f.read()

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

# 5. Modify CupSeasonSurface
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

# 6. Modify HybridSeasonSurface
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
