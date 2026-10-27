export function Logo({ size = 24 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="7" fill="var(--accent)" />
      <rect x="7" y="8" width="5" height="16" rx="1.5" fill="#fff" />
      <rect x="14" y="8" width="5" height="11" rx="1.5" fill="#fff" />
      <rect x="21" y="8" width="5" height="7" rx="1.5" fill="#fff" />
    </svg>
  );
}
