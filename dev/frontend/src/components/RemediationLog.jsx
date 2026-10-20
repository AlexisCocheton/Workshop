import Card from "./Card.jsx";
import { formatAgo, formatClock } from "../status.js";

// Journal des actions du moteur de remédiation (du plus récent au plus ancien).
export default function RemediationLog({ events }) {
  return (
    <Card title="Remédiation automatique">
      {events.length === 0 ? (
        <p className="text-sm text-slate-500">Aucune action pour l'instant.</p>
      ) : (
        <ol className="space-y-3">
          {events.slice(0, 6).map((e, i) => {
            const restart = e.event === "anomaly";
            const at = Date.parse(e.at);
            return (
              <li key={`${e.at}-${i}`} className="flex items-start gap-3 text-sm">
                <span
                  aria-hidden="true"
                  className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs text-white ${
                    restart ? "bg-status-critical" : "bg-status-good"
                  }`}
                >
                  {restart ? "↻" : "✔"}
                </span>
                <div>
                  <p className="font-medium">{e.action}</p>
                  <p className="text-xs text-slate-500">{formatClock(at)} · {formatAgo(at)}</p>
                </div>
              </li>
            );
          })}
        </ol>
      )}
      <p className="mt-4 text-xs text-slate-500">
        Seul le moteur de remédiation agit sur les conteneurs ; le détecteur se contente de le prévenir.
      </p>
    </Card>
  );
}
