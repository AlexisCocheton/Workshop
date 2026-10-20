import { MASCOT } from "../funMode.js";
import { FEATURE_LABELS, lastIncident, phaseOf, secondsSince } from "../status.js";

// Bandeau principal, lisible à distance (démo, Clip Chrono).
// Chaque phase = une couleur de statut + une icône + un titre : jamais la couleur seule.
const PHASES = {
  nominal: { tone: "good", icon: "✔", title: "Service opérationnel" },
  recovered: { tone: "good", icon: "✔", title: "Service rétabli automatiquement" },
  degraded: { tone: "warning", icon: "⚠", title: "Dégradation détectée" },
  recovering: { tone: "warning", icon: "↻", title: "Reprise en cours" },
  incident: { tone: "critical", icon: "✖", title: "Incident en cours" },
  unknown: { tone: "neutral", icon: "?", title: "Supervision indisponible" },
};

const BANNER_TONES = {
  good: "border-status-good bg-status-good/10",
  warning: "border-status-warning bg-status-warning/15",
  critical: "border-status-critical bg-status-critical/10",
  neutral: "border-slate-400 bg-slate-100",
};

const ICON_TONES = {
  good: "bg-status-good text-white",
  warning: "bg-status-warning text-epsi-ink",
  critical: "bg-status-critical text-white",
  neutral: "bg-slate-400 text-white",
};

function describe(phase, status, events) {
  const incident = lastIncident(events);
  switch (phase) {
    case "incident":
      return `Service de paiement indisponible : remédiation automatique déclenchée${
        incident ? ` il y a ${secondsSince(incident.start)} s` : ""
      }.`;
    case "recovering":
      return "Le service répond de nouveau : vérification avant le retour à la normale.";
    case "degraded":
      return "L'API ne répond plus : confirmation sur 3 mesures avant de déclencher la remédiation.";
    case "recovered":
      return incident?.end
        ? `Rétabli ${Math.round((incident.end - incident.start) / 1000)} s après l'alerte, sans intervention humaine.`
        : "Sans intervention humaine.";
    case "unknown":
      return status?.error || "Le détecteur ne répond pas.";
    default:
      return "Aucune anomalie, ni pour le modèle de détection ni pour le contrôle de santé.";
  }
}

// Ce qui a fait réagir le détecteur : le contrôle de santé, ou l'indicateur le plus inhabituel.
function causeOf(status) {
  if (status?.api_healthy === false) return "API injoignable (contrôle de santé /healthz)";
  const top = status?.top_features?.[0];
  if (status?.score > 0 && top) return `${FEATURE_LABELS[top.name] ?? top.name} inhabituel (z = ${top.zscore})`;
  return null;
}

export default function StatusBanner({ status, events, fun }) {
  const phase = phaseOf(status, events);
  const { tone, icon, title } = PHASES[phase];
  const cause = ["incident", "degraded", "recovering"].includes(phase) ? causeOf(status) : null;
  const mascot = fun ? MASCOT[phase] : null; // mode licorne : le chaton commente l'état

  return (
    // Fond blanc sous la teinte : le décor du mode licorne ne transparaît pas.
    <section aria-live="polite" className="rounded-xl bg-white shadow-sm">
      <div className={`flex items-center gap-5 rounded-xl border-l-8 p-5 ${BANNER_TONES[tone]}`}>
        <span
          aria-hidden="true"
          className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-full font-bold ${
            mascot ? "text-4xl" : "text-2xl"
          } ${ICON_TONES[tone]}`}
        >
          {mascot ? mascot.icon : icon}
        </span>
        <div>
          <p className="text-2xl font-bold sm:text-3xl">{title}</p>
          <p className="mt-1 text-epsi-ink/80">{describe(phase, status, events)}</p>
          {cause && <p className="mt-1 text-sm font-semibold">Cause : {cause}</p>}
          {mascot && <p className="mt-2 text-sm italic text-epsi-ink/70">« {mascot.says} »</p>}
        </div>
      </div>
    </section>
  );
}
