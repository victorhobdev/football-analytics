type EmptyStateProps = {
  title?: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
};

export function EmptyState({
  title = "Sem dados para exibir",
  description = "Ajuste os filtros ou tente novamente mais tarde.",
  actionLabel,
  onAction,
  className,
}: EmptyStateProps) {
  const classes = [
    "rounded-[1.25rem] border border-dashed border-[rgba(191,201,195,0.62)] bg-[rgba(255,255,255,0.72)] p-4 text-center shadow-[0_22px_60px_-50px_rgba(17,28,45,0.18)] sm:rounded-[1.45rem] sm:p-6",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <section className={classes}>
      <h3 className="font-[family:var(--font-profile-headline)] text-xl font-extrabold text-[#111c2d]">
        {title}
      </h3>
      <p className="mt-2 text-sm leading-6 text-[#57657a]">{description}</p>
      {actionLabel && onAction ? (
        <button
          className="button-pill button-pill-secondary mt-4 w-full sm:w-auto"
          onClick={onAction}
          type="button"
        >
          {actionLabel}
        </button>
      ) : null}
    </section>
  );
}
