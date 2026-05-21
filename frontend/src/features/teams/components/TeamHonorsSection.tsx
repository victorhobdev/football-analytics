import type { TeamHonorScope, TeamHonorScopeSummary, TeamHonorsPreview } from "@/features/teams/types";

type TeamHonorsSectionProps = {
  honors: TeamHonorsPreview;
};

const SCOPE_ORDER: TeamHonorScope[] = ["mundial", "continental", "nacional", "estadual"];
const FALLBACK_SCOPE_LABEL: Record<TeamHonorScope, string> = {
  mundial: "Mundial",
  continental: "Continental",
  nacional: "Nacional",
  estadual: "Estadual",
};

function formatInteger(value: number): string {
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 }).format(value);
}

function resolveScopes(honors: TeamHonorsPreview): TeamHonorScopeSummary[] {
  return SCOPE_ORDER.map((scope) => {
    const scopeSummary = honors.scopes.find((item) => item.scope === scope);

    return (
      scopeSummary ?? {
        scope,
        label: FALLBACK_SCOPE_LABEL[scope],
        total: 0,
        items: [],
      }
    );
  });
}

function HonorScopeIcon({
  className,
  scope,
}: {
  className?: string;
  scope: TeamHonorScope;
}) {
  const path =
    scope === "mundial"
      ? "M12 4.5a7.5 7.5 0 1 0 0 15 7.5 7.5 0 0 0 0-15Zm0 0c2 1.9 3 4.4 3 7.5s-1 5.6-3 7.5M12 4.5c-2 1.9-3 4.4-3 7.5s1 5.6 3 7.5M5 12h14"
      : scope === "continental"
        ? "M6 19V5m0 0h10.5l-1.2 3 1.2 3H6"
      : scope === "nacional"
        ? "m12 4 2.2 4.5 5 .7-3.6 3.5.9 5-4.5-2.4L7.5 17l.9-5-3.6-3.5 5-.7L12 4Z"
      : "M12 3.5 18.5 6v5.2c0 3.9-2.5 7.2-6.5 9.3-4-2.1-6.5-5.4-6.5-9.3V6L12 3.5Z";

  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.75"
      viewBox="0 0 24 24"
    >
      <path d={path} />
    </svg>
  );
}

export function TeamHonorsSection({ honors }: TeamHonorsSectionProps) {
  const scopes = resolveScopes(honors);

  return (
    <section className="space-y-3">
      <div>
        <p className="text-[0.7rem] font-bold uppercase tracking-[0.2em] text-white/58">
          Conquistas relevantes
        </p>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-white/62">
          {honors.criterionLabel}
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
        {scopes.map((scope) => {
          const hasTitles = scope.total > 0;
          const visibleItems = scope.items.filter((item) => item.count > 0);

          return (
            <article
              className="flex min-h-[10.75rem] flex-col rounded-[1.25rem] border border-white/14 bg-[linear-gradient(145deg,rgba(255,255,255,0.15),rgba(255,255,255,0.08))] p-4 text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.1)]"
              key={scope.scope}
            >
              <div className="flex items-start justify-between gap-3">
                <p className="text-[0.62rem] font-extrabold uppercase tracking-[0.2em] text-white/52">
                  {scope.label}
                </p>
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/12 text-white/82">
                  <HonorScopeIcon className="h-4 w-4" scope={scope.scope} />
                </span>
              </div>
              <p className="mt-3 min-h-[2rem] font-[family:var(--font-profile-headline)] text-[1.45rem] font-extrabold leading-none text-white">
                {hasTitles ? (
                  <span className="whitespace-nowrap">
                    {formatInteger(scope.total)} {scope.total === 1 ? "título" : "títulos"}
                  </span>
                ) : (
                  "Sem títulos auditados"
                )}
              </p>
              <div className="my-3 h-px bg-white/18" />
              {hasTitles && visibleItems.length > 0 ? (
                <ul className="space-y-1.5 text-sm leading-5 text-white/74">
                  {visibleItems.map((item) => (
                    <li className="flex gap-2" key={`${scope.scope}-${item.label}`}>
                      <span className="shrink-0 font-bold text-white/88">
                        {formatInteger(item.count)} ×
                      </span>
                      <span>{item.label}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </article>
          );
        })}
      </div>
    </section>
  );
}
