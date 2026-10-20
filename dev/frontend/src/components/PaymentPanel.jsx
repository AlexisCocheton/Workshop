import { useState } from "react";
import Card from "./Card.jsx";
import { payDemo } from "../api.js";
import { formatAgo } from "../status.js";

// Preuve que le métier fonctionne : lancer une transaction fictive et voir les dernières.
export default function PaymentPanel({ transactions, onPaid }) {
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  async function pay() {
    setBusy(true);
    try {
      const tx = await payDemo();
      setResult({ ok: true, text: `Transaction acceptée : ${tx.amount.toFixed(2)} ${tx.currency} (id ${tx.id.slice(0, 8)}…)` });
      onPaid();
    } catch (error) {
      setResult({ ok: false, text: `Transaction refusée : ${error.message}` });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Service de paiement">
      <button
        onClick={pay}
        disabled={busy}
        className="rounded-lg bg-epsi-ink px-4 py-2 font-semibold text-white hover:bg-epsi-ink/85 disabled:opacity-60"
      >
        {busy ? "Paiement en cours…" : "Lancer une transaction fictive"}
      </button>
      {result && (
        <p className="mt-3 text-sm font-medium">
          <span aria-hidden="true" className={result.ok ? "text-status-good" : "text-status-critical"}>
            {result.ok ? "✔ " : "✖ "}
          </span>
          {result.text}
        </p>
      )}

      <h3 className="mt-5 text-xs font-semibold uppercase tracking-wide text-slate-500">Dernières transactions</h3>
      {transactions.length === 0 ? (
        <p className="mt-2 text-sm text-slate-500">Aucune transaction.</p>
      ) : (
        <ul className="mt-2 divide-y divide-slate-100 text-sm">
          {transactions.slice(0, 5).map((t) => (
            <li key={t.id} className="flex justify-between gap-3 py-1.5">
              <span className="font-mono text-xs text-slate-500">{t.id.slice(0, 8)}</span>
              <span>{t.amount.toFixed(2)} {t.currency}</span>
              <span className="text-slate-500">{formatAgo(Date.parse(t.created_at))}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
