import { useState } from "react";
import PaymentForm from "./PaymentForm.jsx";
import PaymentPending, { withMinDelay } from "./PaymentPending.jsx";
import { euros, topUp } from "../api.js";

const PRESETS = [10, 20, 50];
const MAX_TOPUP = 500; // même borne que l'API

// Page « Ma cagnotte » : solde, recharge par carte et historique des mouvements.
// Les commandes de la boutique sont ensuite payées avec ce solde.
export default function Wallet({ session, wallet, onExpired, onChanged }) {
  const [amount, setAmount] = useState(20);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null); // { ok, text }

  const amountValid = amount >= 1 && amount <= MAX_TOPUP;

  async function recharge(payment) {
    if (!amountValid) return setMessage({ ok: false, text: `Choisissez un montant entre 1 et ${MAX_TOPUP} €.` });
    setBusy(true);
    setMessage(null);
    try {
      const updated = await withMinDelay(topUp(session.token, amount));
      onChanged(updated);
      setMessage({ ok: true, text: `${euros(amount)} ajoutés avec ${payment.brand} •••• ${payment.last4}.` });
    } catch (e) {
      if (e.status === 401) onExpired();
      const text = e.status >= 500 ? "Paiement momentanément indisponible, réessayez dans quelques instants." : e.message;
      setMessage({ ok: false, text });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label="Ma cagnotte" className="mx-auto grid max-w-4xl gap-6 md:grid-cols-[1fr_340px]">
      <div className="space-y-6">
        <h2 className="text-lg font-bold">Ma cagnotte</h2>
        <Balance label="Solde disponible" amount={wallet?.balance} hint="Vos achats de confiseries sont payés avec ce solde." />
        <MovementList movements={wallet?.movements} />
      </div>

      <div className="h-fit space-y-3 rounded-2xl bg-white p-5 shadow-sm">
        <h3 className="font-bold">Recharger</h3>
        <div className="flex flex-wrap gap-2">
          {PRESETS.map((preset) => (
            <button key={preset} type="button" onClick={() => setAmount(preset)}
              className={`rounded-full px-4 py-1.5 text-sm font-semibold ${amount === preset ? "bg-candy-pink text-white" : "bg-candy-light"}`}>
              {euros(preset)}
            </button>
          ))}
        </div>
        <label className="block text-sm">
          Autre montant (€)
          <input type="number" min={1} max={MAX_TOPUP} step={0.01} value={amount}
            onChange={(e) => setAmount(Number(e.target.value))}
            aria-invalid={!amountValid}
            className="mt-1 w-full rounded-lg border border-candy-light px-3 py-2 text-sm" />
          {!amountValid && <span className="mt-1 block text-xs text-red-700">Entre 1 et {MAX_TOPUP} €.</span>}
        </label>

        {message && <Notice message={message} />}
        <PaymentForm amountLabel={euros(amountValid ? amount : 0)} busy={busy} onSubmit={recharge} />
      </div>

      {busy && <PaymentPending text={`Recharge de ${euros(amount)}. Ne fermez pas la page.`} />}
    </section>
  );
}

export function Balance({ label, amount, hint }) {
  return (
    <div className="rounded-2xl bg-candy-ink p-5 text-white shadow-sm">
      <p className="text-sm text-white/75">{label}</p>
      <p className="mt-1 text-3xl font-bold">{amount === undefined ? "…" : euros(amount)}</p>
      {hint && <p className="mt-2 text-xs text-white/75">{hint}</p>}
    </div>
  );
}

export function Notice({ message }) {
  return (
    <p role="status" className={`rounded-xl px-4 py-2 text-sm font-medium ${message.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
      {message.ok ? "✓ " : "✖ "}{message.text}
    </p>
  );
}

const KINDS = {
  topup: { icon: "💳", text: "Recharge" },
  purchase: { icon: "🛒", text: "Achat" },
  sale: { icon: "🍬", text: "Vente" },
  payout: { icon: "🏦", text: "Virement" },
};

// Derniers mouvements (crédits en vert, débits en prune), du plus récent au plus ancien.
export function MovementList({ movements }) {
  return (
    <div className="rounded-2xl bg-white p-5 shadow-sm">
      <h3 className="font-bold">Historique</h3>
      {movements === undefined ? (
        <p className="mt-3 text-sm text-candy-ink/70">Chargement…</p>
      ) : movements.length === 0 ? (
        <p className="mt-3 text-sm text-candy-ink/70">Aucun mouvement pour le moment.</p>
      ) : (
        <ul className="mt-3 divide-y divide-candy-light text-sm">
          {movements.map((movement, i) => {
            const kind = KINDS[movement.kind] ?? { icon: "•", text: movement.kind };
            return (
              <li key={i} className="flex items-center gap-3 py-2">
                <span aria-hidden="true" className="text-lg">{kind.icon}</span>
                <span className="min-w-0 flex-1">
                  <span className="block font-semibold">{kind.text}</span>
                  <span className="block truncate text-xs text-candy-ink/60">
                    {movement.label} · {new Date(movement.created_at).toLocaleString("fr-FR")}
                  </span>
                </span>
                <span className={`font-bold ${movement.amount > 0 ? "text-green-700" : ""}`}>
                  {movement.amount > 0 ? "+" : "−"}{euros(Math.abs(movement.amount))}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
