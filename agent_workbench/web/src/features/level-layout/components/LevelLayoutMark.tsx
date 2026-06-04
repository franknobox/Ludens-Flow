interface LevelLayoutMarkProps {
  className?: string;
  size?: number;
}

export function LevelLayoutMark({ className, size = 16 }: LevelLayoutMarkProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M4.5 17.25h15"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <path
        d="M6 15.5 12 8l6 7.5"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="m9.1 14.4 2.9-3.35 2.9 3.35"
        fill="currentColor"
        opacity="0.18"
      />
      <path
        d="M7.5 19.75h9"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}
