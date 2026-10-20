import { formatAgo } from "../status.js";

// Une tuile par composant clé : état en un coup d'œil (icône + libellé + couleur).
const TONES = {
  good: "bg-status-good text-white",
  warning: "bg-status-warning text-epsi-ink",
  critical: "bg-status-critical text-white",
  neutral: "bg-slate-300 text-white",
};

const STATE_LABELS = { normal: "Normal", anomaly: "Anomalie", unknown: "Inconnu", no_model: "Sans modèle", starting: "Démarrage" };

function Tile({ label, value, detail, icon, tone }) {
  return (
    <div className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-epsi-ink/5">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-2 flex items-center gap-2 text-xl font-bold">
        <span aria-hidden="true" className={`flex h-6 w-6 items-center justify-center rounded-full text-xs ${TONES[tone]}`}>
          {icon}
        </span>
        {value}
      </p>
      <p className="mt-1 text-xs text-slate-500">{detail}</p>
    </div>
  );
}

export default function ServiceCards({ status, events }) {
  const healthy = status?.api_healthy;
  const lastAction = events[0];
  const restarted = lastAction?.event === "anomaly";
  const blocks = Math.round(status?.values?.waf_blocks ?? 0);

  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <Tile
        label="API de paiement"
        value={healthy == null ? "—" : healthy ? "En ligne" : "Injoignable"}
        icon={healthy === false ? "✖" : "✔"}
        tone={healthy == null ? "neutral" : healthy ? "good" : "critical"}
        detail="Contrôle /healthz toutes les 5 s"
      />
      <Tile
        label="Détecteur IA"
        value={STATE_LABELS[status?.state] ?? "—"}
        icon={status?.state === "anomaly" ? "!" : "✔"}
        tone={status?.state === "anomaly" ? "critical" : status?.state === "normal" ? "good" : "neutral"}
        detail={status?.score != null ? `Score ${status.score.toFixed(2)} (anormal au-dessus de 0)` : "En attente de mesures"}
      />
      <Tile
        label="Remédiation"
        value={lastAction ? (restarted ? "Redémarrage" : "Rétabli") : "En veille"}
        icon={restarted ? "↻" : "✔"}
        tone={lastAction ? (restarted ? "warning" : "good") : "neutral"}
        detail={lastAction ? `Dernière action ${formatAgo(Date.parse(lastAction.at))}` : "Aucune action pour l'instant"}
      />
      <Tile
        label="WAF"
        value={`${blocks} blocage${blocks > 1 ? "s" : ""}`}
        icon="⛨"
        tone={blocks > 0 ? "warning" : "good"}
        detail="Requêtes malveillantes, 30 dernières secondes"
      />
    </div>
  );
}
