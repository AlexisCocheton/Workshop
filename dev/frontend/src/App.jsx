import { useEffect, useState } from "react";
import { fetchEvents, fetchStatus, fetchTransactions, fetchWafBlocks } from "./api.js";
import { useFunMode } from "./funMode.js";
import { formatClock, phaseOf } from "./status.js";
import Assistant from "./components/Assistant.jsx";
import Features from "./components/Features.jsx";
import { FloatingFriends, UnicornParade } from "./components/Friends.jsx";
import Login from "./components/Login.jsx";
import PaymentPanel from "./components/PaymentPanel.jsx";
import RemediationLog from "./components/RemediationLog.jsx";
import ServiceCards from "./components/ServiceCards.jsx";
import StatusBanner from "./components/StatusBanner.jsx";
import Timeline from "./components/Timeline.jsx";
import WafBlocks from "./components/WafBlocks.jsx";

const WINDOW_MS = 5 * 60 * 1000; // historique gardé pour le graphique : 5 minutes

export default function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem("auth_token"));

  if (!token) {
    return <Login onLogin={(t) => { sessionStorage.setItem("auth_token", t); setToken(t); }} />;
  }

  return <Dashboard onLogout={() => { sessionStorage.removeItem("auth_token"); setToken(null); }} />;
}

function Dashboard({ onLogout }) {
  const [status, setStatus] = useState(null);
  const [events, setEvents] = useState([]);
  const [wafBlocks, setWafBlocks] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [history, setHistory] = useState([]);
  const [updatedAt, setUpdatedAt] = useState(null);
  const [fun, setFun] = useFunMode();

  // Toutes les 2 s : état du détecteur (avec historique) et journal de remédiation.
  useEffect(() => {
    async function refresh() {
      try {
        const current = await fetchStatus();
        const now = Date.now();
        setStatus(current);
        setUpdatedAt(now);
        setHistory((h) =>
          [...h, { t: now, score: current.score, state: current.state, apiHealthy: current.api_healthy }].filter(
            (p) => p.t > now - WINDOW_MS,
          ),
        );
      } catch {
        setStatus({ state: "unknown", error: "Le détecteur ne répond pas." });
      }
      try {
        setEvents(await fetchEvents());
      } catch {
        // Remédiation injoignable : on garde le dernier journal connu.
      }
      try {
        setWafBlocks(await fetchWafBlocks());
      } catch {
        // Détecteur injoignable : on garde la dernière liste connue.
      }
    }
    refresh();
    const timer = setInterval(refresh, 2000);
    return () => clearInterval(timer);
  }, []);

  // Toutes les 5 s : dernières transactions (preuve que le paiement fonctionne).
  const refreshTransactions = () => fetchTransactions().then(setTransactions).catch(() => {});
  useEffect(() => {
    refreshTransactions();
    const timer = setInterval(refreshTransactions, 5000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="relative min-h-screen bg-epsi-bg text-epsi-ink">
      {fun && <FloatingFriends />}
      {fun && <UnicornParade phase={phaseOf(status, events)} />}

      <div className="relative z-10 mx-auto max-w-6xl space-y-5 px-4 py-6">
        <header className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-epsi-ink/60">Project Resilience-Alpha</p>
            <h1 className="text-2xl font-bold sm:text-3xl">Supervision de la plateforme de paiement</h1>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              aria-pressed={fun}
              onClick={() => setFun(!fun)}
              className="rounded-full bg-white px-3 py-1 text-sm shadow-sm ring-1 ring-epsi-ink/10 hover:bg-epsi-accent/30"
            >
              🦄 Mode licorne : {fun ? "activé" : "désactivé"}
            </button>
            <button
              type="button"
              onClick={onLogout}
              className="rounded-full border border-epsi-ink/20 px-3 py-1 text-sm text-epsi-ink/70 hover:bg-red-50 hover:text-red-600"
            >
              Déconnexion
            </button>
            <p className="flex items-center gap-2 text-sm text-epsi-ink/70">
              <span className="relative flex h-2.5 w-2.5" aria-hidden="true">
                <span className="absolute h-full w-full rounded-full bg-status-good opacity-60 motion-safe:animate-ping" />
                <span className="relative h-2.5 w-2.5 rounded-full bg-status-good" />
              </span>
              En direct{updatedAt && ` · mis à jour à ${formatClock(updatedAt)}`}
            </p>
          </div>
        </header>

        <StatusBanner status={status} events={events} fun={fun} />
        <ServiceCards status={status} events={events} wafBlocks={wafBlocks} />
        <Timeline history={history} events={events} />

        <div className="grid gap-5 lg:grid-cols-2">
          <Features status={status} />
          <RemediationLog events={events} />
        </div>

        <div className="grid gap-5 lg:grid-cols-2">
          <WafBlocks blocks={wafBlocks} />
          <PaymentPanel transactions={transactions} onPaid={refreshTransactions} />
        </div>

        <div className="grid gap-5 lg:grid-cols-2">
          <Assistant />
        </div>
      </div>
    </div>
  );
}
