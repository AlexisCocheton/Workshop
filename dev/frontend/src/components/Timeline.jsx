import { useState } from "react";
import Card from "./Card.jsx";
import { formatClock } from "../status.js";

// Graphique « avant / pendant / après » sur les 5 dernières minutes :
// score du détecteur, seuil d'alerte, périodes d'incident, actions de
// remédiation, et frise de disponibilité de l'API.
const WINDOW_MS = 5 * 60 * 1000;
const POLL_MS = 2000; // fréquence de rafraîchissement du dashboard
const W = 800; // largeur du repère SVG (le navigateur le met à l'échelle)
const H = 220;
const M = { top: 18, right: 56, bottom: 28, left: 44 };
const STRIP_H = 30;

const COLORS = {
  line: "#2a78d6",
  critical: "#d03b3b",
  grid: "#e1e0d9",
  axis: "#c3c2b7",
  muted: "#898781",
  ink: "#261E48",
};

// Regroupe les mesures consécutives qui vérifient `predicate` en périodes [start, end].
function periods(history, predicate) {
  const out = [];
  let current = null;
  for (const point of history) {
    if (predicate(point)) {
      if (!current) {
        current = { start: point.t, end: point.t };
        out.push(current);
      }
      current.end = point.t + POLL_MS;
    } else {
      current = null;
    }
  }
  return out;
}

function ticks(lo, hi) {
  const step = [2, 5, 10, 20, 50, 100].find((s) => (hi - lo) / s <= 6) ?? 200;
  const values = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) values.push(v);
  return values;
}

export default function Timeline({ history, events }) {
  const [hover, setHover] = useState(null);
  const points = history.filter((p) => p.score != null);

  if (points.length < 2) {
    return (
      <Card title="Avant, pendant, après : les 5 dernières minutes">
        <p className="text-sm text-slate-500">Collecte des premières mesures…</p>
      </Card>
    );
  }

  const now = Date.now();
  const start = now - WINDOW_MS;
  const plotW = W - M.left - M.right;
  const x = (t) => M.left + ((Math.min(t, now) - start) / WINDOW_MS) * plotW;

  const scores = points.map((p) => p.score);
  const lo = Math.min(-10, ...scores);
  const hi = Math.max(10, ...scores);
  const pad = (hi - lo) * 0.08;
  const y = (v) => M.top + ((hi + pad - v) / (hi - lo + 2 * pad)) * (H - M.top - M.bottom);

  const path = points.map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)},${y(p.score).toFixed(1)}`).join(" ");
  const last = points[points.length - 1];
  const incidents = periods(history, (p) => p.state === "anomaly");
  const outages = periods(history, (p) => p.apiHealthy === false);
  const actions = events
    .map((e) => ({ t: Date.parse(e.at), restart: e.event === "anomaly" }))
    .filter((a) => a.t >= start);
  const hovered = hover != null ? points[hover] : null;

  // Réticule : on cherche la mesure la plus proche du pointeur sur l'axe du temps.
  function onPointerMove(event) {
    const rect = event.currentTarget.getBoundingClientRect();
    const pointerX = ((event.clientX - rect.left) / rect.width) * W;
    let best = 0;
    points.forEach((p, i) => {
      if (Math.abs(x(p.t) - pointerX) < Math.abs(x(points[best].t) - pointerX)) best = i;
    });
    setHover(best);
  }

  return (
    <Card title="Avant, pendant, après : les 5 dernières minutes">
      <div className="relative">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="h-auto w-full touch-none"
          role="img"
          aria-label={`Score d'anomalie du détecteur, dernière valeur ${last.score.toFixed(1)}, ${incidents.length} période(s) d'incident.`}
          onPointerMove={onPointerMove}
          onPointerLeave={() => setHover(null)}
        >
          {incidents.map((p, i) => (
            <g key={`incident-${i}`}>
              <rect x={x(p.start)} y={M.top} width={Math.max(3, x(p.end) - x(p.start))} height={H - M.top - M.bottom} fill={COLORS.critical} opacity="0.1" />
              <text x={x(p.start) + 4} y={M.top + 12} fontSize="11" fill={COLORS.ink}>Incident</text>
            </g>
          ))}

          {ticks(lo, hi).map((v) => (
            <g key={v}>
              <line x1={M.left} x2={W - M.right} y1={y(v)} y2={y(v)} stroke={COLORS.grid} strokeWidth="1" />
              <text x={M.left - 8} y={y(v) + 4} fontSize="11" textAnchor="end" fill={COLORS.muted}>{v}</text>
            </g>
          ))}

          {/* Seuil d'alerte : au-dessus de 0, le modèle juge la mesure anormale. */}
          <line x1={M.left} x2={W - M.right} y1={y(0)} y2={y(0)} stroke={COLORS.critical} strokeWidth="1.5" />
          <text x={M.left + 4} y={y(0) - 5} fontSize="11" fill={COLORS.ink}>seuil d'alerte</text>

          {actions.map((a, i) => (
            <g key={`action-${i}`}>
              <line x1={x(a.t)} x2={x(a.t)} y1={M.top} y2={H - M.bottom} stroke={COLORS.ink} strokeWidth="1" opacity="0.45" />
              <text x={x(a.t) + 4} y={a.restart ? M.top + 28 : H - M.bottom - 6} fontSize="11" fill={COLORS.ink}>
                {a.restart ? "↻ redémarrage" : "✔ rétabli"}
              </text>
            </g>
          ))}

          <path d={path} fill="none" stroke={COLORS.line} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
          <circle cx={x(last.t)} cy={y(last.score)} r="4" fill={COLORS.line} stroke="#fff" strokeWidth="2" />
          <text x={x(last.t) + 8} y={y(last.score) + 4} fontSize="12" fontWeight="600" fill={COLORS.ink}>{last.score.toFixed(1)}</text>

          <line x1={M.left} x2={W - M.right} y1={H - M.bottom} y2={H - M.bottom} stroke={COLORS.axis} strokeWidth="1" />
          {[5, 4, 3, 2, 1, 0].map((minutes) => (
            <text key={minutes} x={x(now - minutes * 60_000)} y={H - 8} fontSize="11" textAnchor="middle" fill={COLORS.muted}>
              {minutes ? `−${minutes} min` : "maintenant"}
            </text>
          ))}

          {hovered && (
            <g>
              <line x1={x(hovered.t)} x2={x(hovered.t)} y1={M.top} y2={H - M.bottom} stroke={COLORS.ink} strokeWidth="1" />
              <circle cx={x(hovered.t)} cy={y(hovered.score)} r="4" fill={COLORS.line} stroke="#fff" strokeWidth="2" />
            </g>
          )}
        </svg>

        {hovered && (
          <div
            className="pointer-events-none absolute top-0 rounded-md bg-white px-3 py-2 text-xs shadow-lg ring-1 ring-black/10"
            style={{
              left: `${(x(hovered.t) / W) * 100}%`,
              transform: x(hovered.t) > W * 0.65 ? "translateX(calc(-100% - 12px))" : "translateX(12px)",
            }}
          >
            <p className="font-semibold">{formatClock(hovered.t)}</p>
            <p>Score : {hovered.score.toFixed(2)}</p>
            <p>Détecteur : {hovered.state}</p>
            <p>API : {hovered.apiHealthy === false ? "injoignable" : "en ligne"}</p>
          </div>
        )}
      </div>

      {/* Frise de disponibilité : piste neutre = API en ligne, rouge = API injoignable. */}
      <svg viewBox={`0 0 ${W} ${STRIP_H}`} className="h-auto w-full" role="img" aria-label={`Disponibilité de l'API : ${outages.length} coupure(s).`}>
        <text x={M.left - 8} y={19} fontSize="11" textAnchor="end" fill={COLORS.muted}>API</text>
        <rect x={x(history[0].t)} y={8} width={Math.max(0, x(now) - x(history[0].t))} height={14} rx="4" fill={COLORS.grid} />
        {outages.map((o, i) => (
          <rect key={i} x={x(o.start)} y={8} width={Math.max(3, x(o.end) - x(o.start))} height={14} rx="4" fill={COLORS.critical} />
        ))}
      </svg>

      <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-600">
        <li className="flex items-center gap-1.5"><span className="h-0.5 w-4 bg-[#2a78d6]" aria-hidden="true" />Score d'anomalie</li>
        <li className="flex items-center gap-1.5"><span className="h-0.5 w-4 bg-status-critical" aria-hidden="true" />Seuil d'alerte (0)</li>
        <li className="flex items-center gap-1.5"><span className="h-3 w-4 bg-status-critical/10 ring-1 ring-status-critical/30" aria-hidden="true" />Incident (détecteur en alerte)</li>
        <li className="flex items-center gap-1.5"><span className="h-3 w-4 rounded-sm bg-status-critical" aria-hidden="true" />API injoignable</li>
      </ul>

      <details className="mt-3 text-sm">
        <summary className="cursor-pointer text-epsi-ink/70">Voir les dernières mesures (tableau)</summary>
        <table className="mt-2 w-full text-left text-xs">
          <thead className="text-slate-500">
            <tr><th className="py-1">Heure</th><th>Score</th><th>Détecteur</th><th>API</th></tr>
          </thead>
          <tbody>
            {points.slice(-10).reverse().map((p) => (
              <tr key={p.t} className="border-t border-slate-100">
                <td className="py-1">{formatClock(p.t)}</td>
                <td>{p.score.toFixed(2)}</td>
                <td>{p.state}</td>
                <td>{p.apiHealthy === false ? "injoignable" : "en ligne"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </Card>
  );
}
