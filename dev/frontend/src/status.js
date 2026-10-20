// Logique d'affichage partagée : phase de l'incident, libellés, formats d'heure.

export const FEATURE_LABELS = {
  req_rate: "Débit de requêtes (/s)",
  err_4xx_rate: "Erreurs client 4xx (/s)",
  err_5xx_rate: "Erreurs serveur 5xx (/s)",
  api_cpu: "CPU de l'API",
  waf_blocks: "Blocages WAF (30 s)",
};

// Phase affichée par le bandeau, déduite du détecteur et du journal de remédiation
// (événements du plus récent au plus ancien).
export function phaseOf(status, events) {
  if (!status || ["starting", "unknown", "no_model"].includes(status.state)) return "unknown";
  if (status.state === "anomaly") return status.api_healthy ? "recovering" : "incident";
  if (status.api_healthy === false) return "degraded";
  const last = events[0];
  if (last?.event === "recovered" && Date.now() - Date.parse(last.at) < 60_000) return "recovered";
  return "nominal";
}

// Dernier incident : heure de l'alerte et, s'il est terminé, heure du retour à la normale.
export function lastIncident(events) {
  const alert = events.find((e) => e.event === "anomaly");
  if (!alert) return null;
  const start = Date.parse(alert.at);
  const recovery = events.find((e) => e.event === "recovered" && Date.parse(e.at) >= start);
  return { start, end: recovery ? Date.parse(recovery.at) : null };
}

export const formatClock = (ms) => new Date(ms).toLocaleTimeString("fr-FR");
export const secondsSince = (ms) => Math.max(0, Math.round((Date.now() - ms) / 1000));

export function formatAgo(ms) {
  const seconds = secondsSince(ms);
  if (seconds < 60) return `il y a ${seconds} s`;
  if (seconds < 3600) return `il y a ${Math.floor(seconds / 60)} min`;
  return `à ${formatClock(ms)}`;
}
