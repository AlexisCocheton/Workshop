import { useEffect, useState } from "react";

// Décor du mode licorne, purement décoratif (masqué aux lecteurs d'écran).

const FRIENDS = ["🦄", "🐱", "🌈", "😺", "✨", "🦄", "🐈", "💖", "🦄", "😸", "🌟", "🐱"];

// Chatons et licornes qui flottent doucement derrière les blocs.
export function FloatingFriends() {
  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
      {FRIENDS.map((emoji, i) => (
        <span
          key={i}
          className="friend absolute text-4xl opacity-40"
          style={{
            left: `${(i * 37 + 5) % 95}%`,
            top: `${(i * 53 + 10) % 90}%`,
            animationDelay: `${(i % 6) * 0.7}s`,
            animationDuration: `${3 + (i % 4)}s`,
          }}
        >
          {emoji}
        </span>
      ))}
    </div>
  );
}

// Quand le service vient d'être rétabli, une licorne traverse l'écran.
export function UnicornParade({ phase }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (phase !== "recovered") return;
    setVisible(true);
    const timer = setTimeout(() => setVisible(false), 4500);
    return () => clearTimeout(timer);
  }, [phase]);

  if (!visible) return null;
  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-x-0 top-1/3 z-50 overflow-hidden">
      <span className="gallop inline-block whitespace-nowrap text-7xl">🦄🌈✨</span>
    </div>
  );
}
