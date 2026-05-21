import Image from "next/image";

type CoachAvatarProps = {
  coachName: string;
  photoUrl?: string | null;
  hasRealPhoto: boolean;
  size?: "card" | "profile";
};

const SIZE_CONFIG = {
  card: {
    className: "h-14 w-14 text-sm",
    pixels: 56,
  },
  profile: {
    className: "h-20 w-20 text-lg",
    pixels: 80,
  },
} as const;

function getCoachInitials(coachName: string): string {
  const tokens = coachName
    .replace(/^(Unknown Coach|Nome pendente) #/i, "")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2);

  if (tokens.length === 0) {
    return "TC";
  }

  return tokens.map((token) => token[0]?.toUpperCase() ?? "").join("");
}

export function CoachAvatar({
  coachName,
  photoUrl,
  hasRealPhoto,
  size = "card",
}: CoachAvatarProps) {
  const { className: sizeClassName, pixels } = SIZE_CONFIG[size];

  if (hasRealPhoto && photoUrl) {
    return (
      <div
        className={`${sizeClassName} relative shrink-0 overflow-hidden rounded-full border border-white/20 shadow-[0_16px_34px_-24px_rgba(17,28,45,0.42)]`}
      >
        <Image
          alt={`Foto de ${coachName}`}
          className="object-cover"
          height={pixels}
          referrerPolicy="no-referrer"
          src={photoUrl}
          unoptimized
          width={pixels}
        />
      </div>
    );
  }

  return (
    <div
      aria-label={`Foto indisponível de ${coachName}`}
      className={`${sizeClassName} flex shrink-0 items-center justify-center rounded-full border border-[rgba(191,201,195,0.7)] bg-[radial-gradient(circle_at_30%_20%,rgba(166,242,209,0.8),transparent_42%),linear-gradient(135deg,rgba(235,241,252,0.98),rgba(245,247,250,0.98))] px-2 text-center font-extrabold uppercase tracking-[0.08em] text-[#003526] shadow-[inset_0_1px_0_rgba(255,255,255,0.82),0_16px_34px_-28px_rgba(17,28,45,0.38)]`}
      role="img"
    >
      <span>{getCoachInitials(coachName)}</span>
    </div>
  );
}
