import Card from "./Card.jsx";
import { formatAgo } from "../status.js";

// Requêtes bloquées par le WAF (type, URL tentée, IP source), lues dans Loki
// via le détecteur. Montre CE qui a été bloqué, pas seulement combien.
export default function WafBlocks({ blocks }) {
  return (
    <Card title="Requêtes bloquées par le WAF">
      {blocks.length === 0 ? (
        <p className="text-sm text-slate-500">Aucune requête bloquée récemment.</p>
      ) : (
        <ul className="space-y-2">
          {blocks.slice(0, 6).map((b, i) => (
            <li key={`${b.at}-${i}`} className="flex items-start gap-2 text-sm">
              <span
                aria-hidden="true"
                className="mt-0.5 shrink-0 rounded-full bg-status-critical px-2 py-0.5 text-xs text-white"
              >
                {b.type}
              </span>
              <div className="min-w-0">
                {/* URL tentée : tronquée visuellement si longue, mais complète dans le titre. */}
                <p className="truncate font-mono text-xs text-epsi-ink" title={b.uri}>
                  {b.method} {b.uri}
                </p>
                <p className="text-xs text-slate-500">
                  source {b.client_ip} · {formatAgo(Date.parse(b.at))}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-4 text-xs text-slate-500">
        Le WAF bloque ces requêtes (403) en frontal ; elles n'atteignent jamais l'API.
      </p>
    </Card>
  );
}
