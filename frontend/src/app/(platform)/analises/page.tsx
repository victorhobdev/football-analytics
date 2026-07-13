const powerBiEmbedUrl =
  process.env.NEXT_PUBLIC_POWER_BI_EMBED_URL?.trim() ||
  "https://app.powerbi.com/view?r=eyJrIjoiZjI0MzhlOTMtMzE0Mi00NmY2LWJlNmMtMDRiZTc2YmNmZjBhIiwidCI6IjE0MDAyMTc4LWEwZDAtNGYxNC1iZGQ2LTJiMjNiYTJiNThkYyJ9";

export default function AnalisesPage() {
  return (
    <section className="overflow-hidden rounded-[1.5rem] border border-[rgba(17,28,45,0.1)] bg-white shadow-[0_20px_48px_-40px_rgba(17,28,45,0.35)]">
      <iframe
        allowFullScreen
        className="h-[calc(100dvh-8rem)] min-h-[34rem] w-full border-0 lg:h-[calc(100dvh-10rem)]"
        loading="lazy"
        src={powerBiEmbedUrl}
        title="Football Analytics — Análises Competitivas"
      />
    </section>
  );
}
