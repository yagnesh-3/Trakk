import { initials } from "../lib/format";
import type { UserRef } from "../lib/types";

const HUES = [12, 38, 145, 175, 200, 230, 265, 300, 330];

export function Avatar({ user, size = 28 }: { user: UserRef | null; size?: number }) {
  if (!user) {
    return (
      <span className="avatar avatar-empty" style={{ width: size, height: size }} title="Unassigned">
        ?
      </span>
    );
  }
  const hue = HUES[user.id % HUES.length];
  return (
    <span
      className="avatar"
      style={{
        width: size,
        height: size,
        fontSize: size * 0.4,
        background: `hsl(${hue} 55% 45%)`,
      }}
      title={user.name}
    >
      {initials(user.name)}
    </span>
  );
}
