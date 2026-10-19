import { useEffect, useState } from "react";

// Le navigateur passe par le WAF pour l'API, et joint directement les services
// de supervision publiés sur l'hôte. Les URLs sont configurables (variables
// VITE_*) pour s'adapter aux ports réels de la machine ; valeurs par défaut =
// ports du compose.yml.
const WAF = import.meta.env.VITE_WAF_URL || "http://localhost:8080";
const DETECTOR = import.meta.env.VITE_DETECTOR_URL || "http://localhost:8000";
const REMEDIATION = import.meta.env.VITE_REMEDIATION_URL || "http://localhost:8200";

const COLORS = {
  normal: "bg-green-100 text-green-800",
  anomaly: "bg-red-100 text-red-800",
  unknown: "bg-yellow-100 text-yellow-800",
  no_model: "bg-gray-200 text-gray-700",
  starting: "bg-gray-200 text-gray-700",
};

async function getJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export default function App() {
  const [status, setStatus] = useState({ state: "starting" });
  const [events, setEvents] = useState([]);
  const [result, setResult] = useState("");

  // Rafraîchit l'état du détecteur et l'historique de remédiation toutes les 2 s.
  useEffect(() => {
    const refresh = async () => {
      try { setStatus(await getJson(`${DETECTOR}/status`)); } catch { setStatus({ state: "unknown" }); }
      try { setEvents(await getJson(`${REMEDIATION}/events`)); } catch { setEvents([]); }
    };
    refresh();
    const timer = setInterval(refresh, 2000);
    return () => clearInterval(timer);
  }, []);

  // Démontre que le service de paiement fonctionne : login puis transaction.
  const runTransaction = async () => {
    setResult("…");
    try {
      const { token } = await getJson(`${WAF}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user: "app", password: "app" }),
      });
      const tx = await getJson(`${WAF}/transactions`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ amount: 42.5, currency: "EUR" }),
      });
      setResult(`Transaction ${tx.status} (id ${tx.id.slice(0, 8)}…)`);
    } catch (error) {
      setResult(`Échec : ${error.message}`);
    }
  };

  const badge = COLORS[status.state] || COLORS.unknown;

  return (
    <div className="min-h-screen bg-slate-50 p-6 text-slate-800">
      <div className="mx-auto max-w-3xl space-y-6">
        <h1 className="text-2xl font-bold">RESILIENCE-ALPHA — Supervision</h1>

        <section className="rounded-lg bg-white p-5 shadow">
          <h2 className="mb-3 font-semibold">État du détecteur d'anomalies</h2>
          <span className={`rounded px-3 py-1 text-sm font-medium ${badge}`}>{status.state}</span>
          {status.score != null && <span className="ml-3 text-sm">score : {status.score}</span>}
          {status.api_healthy != null && (
            <span className="ml-3 text-sm">
              API : {status.api_healthy ? "✅ en ligne" : "❌ injoignable"}
            </span>
          )}
          {status.top_features?.length > 0 && (
            <ul className="mt-3 text-sm text-slate-600">
              {status.top_features.map((feature) => (
                <li key={feature.name}>
                  {feature.name} = {Number(feature.value).toFixed(2)} (z = {feature.zscore})
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="rounded-lg bg-white p-5 shadow">
          <h2 className="mb-3 font-semibold">Service de paiement</h2>
          <button onClick={runTransaction} className="rounded bg-indigo-600 px-4 py-2 text-white hover:bg-indigo-700">
            Lancer une transaction fictive
          </button>
          {result && <p className="mt-3 text-sm">{result}</p>}
        </section>

        <section className="rounded-lg bg-white p-5 shadow">
          <h2 className="mb-3 font-semibold">Remédiation automatique</h2>
          {events.length === 0 ? (
            <p className="text-sm text-slate-500">Aucune action pour l'instant.</p>
          ) : (
            <ul className="space-y-1 text-sm">
              {events.map((event, index) => (
                <li key={index} className="text-slate-600">
                  <span className="text-slate-400">{event.at.slice(11, 19)}</span> — {event.action}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
