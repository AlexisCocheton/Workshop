import { useState } from "react";
import PaymentPending, { withMinDelay } from "./PaymentPending.jsx";
import { Balance, MovementList, Notice } from "./Wallet.jsx";
import { euros, payout } from "../api.js";

const input = "mt-1 w-full rounded-lg border border-candy-light px-3 py-2 text-sm";

// IBAN affiché par groupes de 4, comme sur un RIB. L'API revérifie la clé (modulo 97).
const formatIban = (value) => value.replace(/[^0-9a-z]/gi, "").toUpperCase().slice(0, 34).replace(/(.{4})(?=.)/g, "$1 ");

// Page « Épargne » du marchand : chaque vente la crédite ; il la vire vers son compte bancaire.
export default function Savings({ session, wallet, onExpired, onChanged }) {
  const [form, setForm] = useState({ holder: "", iban: "", amount: "" });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null); // { ok, text }
  const field = (key, format = (v) => v) => ({ value: form[key], onChange: (e) => setForm({ ...form, [key]: format(e.target.value) }) });

  const balance = wallet?.balance ?? 0;
  const amount = Number(form.amount);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      const updated = await withMinDelay(payout(session.token, { amount, iban: form.iban, holder: form.holder }));
      onChanged(updated);
      setMessage({ ok: true, text: `Virement de ${euros(amount)} envoyé vers ${form.iban.slice(0, 4)} •••• ${form.iban.replace(/ /g, "").slice(-4)}.` });
      setForm({ ...form, amount: "" }); // garde titulaire et IBAN pour le prochain virement
    } catch (e) {
      if (e.status === 401) onExpired();
      setMessage({ ok: false, text: e.message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label="Épargne" className="mx-auto grid max-w-4xl gap-6 md:grid-cols-[1fr_340px]">
      <div className="space-y-6">
        <h2 className="text-lg font-bold">Épargne</h2>
        <Balance label="Épargne disponible" amount={wallet?.balance} hint="Créditée à chaque commande payée par un client." />
        <MovementList movements={wallet?.movements} />
      </div>

      <form onSubmit={submit} className="h-fit space-y-3 rounded-2xl bg-white p-5 shadow-sm">
        <h3 className="font-bold">Virement vers mon compte bancaire</h3>
        {message && <Notice message={message} />}
        <label className="block text-sm">
          Titulaire du compte
          <input required maxLength={80} autoComplete="name" className={input} {...field("holder")} />
        </label>
        <label className="block text-sm">
          IBAN
          <input required className={`${input} font-mono`} placeholder="FR76 3000 6000 0112 3456 7890 189"
            autoComplete="off" spellCheck={false} {...field("iban", formatIban)} />
        </label>
        <label className="block text-sm">
          Montant (€)
          <span className="mt-1 flex gap-2">
            <input required type="number" min={0.01} max={balance} step={0.01}
              className="w-full rounded-lg border border-candy-light px-3 py-2 text-sm" {...field("amount")} />
            <button type="button" disabled={balance <= 0} onClick={() => setForm({ ...form, amount: String(balance) })}
              className="shrink-0 rounded-full bg-candy-light px-3 text-xs font-semibold disabled:opacity-50">
              Tout virer
            </button>
          </span>
        </label>
        <button disabled={busy || balance <= 0}
          className="w-full rounded-full bg-candy-ink px-4 py-2.5 font-semibold text-white hover:bg-candy-ink/85 disabled:opacity-60">
          {amount > 0 ? `Virer ${euros(amount)}` : "Virer"}
        </button>
        <p className="text-xs text-candy-ink/60">🔒 Boutique fictive : aucun virement réel n'est émis.</p>
      </form>

      {busy && <PaymentPending title="Virement en cours…" text={`Virement de ${euros(amount)} vers votre compte bancaire.`} />}
    </section>
  );
}
