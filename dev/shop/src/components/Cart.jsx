import { useState } from "react";
import AuthForm from "./AuthForm.jsx";
import PaymentPending, { withMinDelay } from "./PaymentPending.jsx";
import QuantityInput from "./QuantityInput.jsx";
import { euros, placeOrder } from "../api.js";

// Panier et paiement avec la cagnotte. Le total affiché est indicatif : l'API
// recalcule avec ses propres prix et refuse (402) si la cagnotte ne suffit pas.
export default function Cart({ products, cart, onQuantity, session, balance, onLogin, onExpired, onOrdered, onRecharge }) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null); // succès : { ok, order } ; échec : { ok, text }

  const lines = products.filter((p) => cart[p.id]).map((p) => ({ ...p, quantity: cart[p.id] }));
  const total = lines.reduce((sum, line) => sum + line.price * line.quantity, 0);
  const missing = balance === undefined ? 0 : total - balance;

  async function checkout() {
    setBusy(true);
    setResult(null);
    try {
      const order = await withMinDelay(placeOrder(session.token, cart));
      setResult({ ok: true, order });
      onOrdered();
    } catch (error) {
      if (error.status === 401) onExpired();
      // 5xx : c'est ce que voit le client pendant l'incident, avant la reprise automatique.
      const text = error.status >= 500 ? "Paiement momentanément indisponible, réessayez dans quelques instants." : error.message;
      setResult({ ok: false, text });
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className="h-fit rounded-2xl bg-white p-5 shadow-sm lg:sticky lg:top-6">
      <h2 className="text-lg font-bold">Mon panier</h2>

      {lines.length === 0 ? (
        <p className="mt-3 text-sm text-candy-ink/70">Votre panier est vide.</p>
      ) : (
        <ul className="mt-3 divide-y divide-candy-light">
          {lines.map((line) => (
            <li key={line.id} className="flex items-center gap-2 py-2 text-sm">
              <span aria-hidden="true">{line.emoji}</span>
              <span className="flex-1">{line.name}</span>
              <button aria-label={`Retirer un ${line.name}`} className="h-7 w-7 rounded-full bg-candy-light font-bold"
                onClick={() => onQuantity(line.id, line.quantity - 1)}>−</button>
              <QuantityInput quantity={line.quantity} stock={line.stock} label={line.name}
                onChange={(quantity) => onQuantity(line.id, quantity)} />
              <button aria-label={`Ajouter un ${line.name}`} className="h-7 w-7 rounded-full bg-candy-light font-bold disabled:opacity-40"
                disabled={line.quantity >= line.stock} onClick={() => onQuantity(line.id, line.quantity + 1)}>+</button>
            </li>
          ))}
        </ul>
      )}

      {lines.length > 0 && (
        <p className="mt-3 flex justify-between border-t border-candy-light pt-3 font-bold">
          <span>Total</span>
          <span>{euros(total)}</span>
        </p>
      )}

      {lines.length > 0 && !session && <AuthForm onLogin={onLogin} />}
      {lines.length > 0 && session && (
        <div className="mt-4 space-y-3">
          <p className="flex justify-between text-sm">
            <span className="text-candy-ink/70">Ma cagnotte</span>
            <span className="font-semibold">{balance === undefined ? "…" : euros(balance)}</span>
          </p>
          {missing > 0 ? (
            <>
              <p className="rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-800">
                Il manque {euros(missing)} dans votre cagnotte pour cette commande.
              </p>
              <button onClick={onRecharge}
                className="w-full rounded-full bg-candy-pink px-4 py-2.5 font-semibold text-white hover:bg-candy-pink/85">
                Recharger ma cagnotte
              </button>
            </>
          ) : (
            <button onClick={checkout} disabled={busy || balance === undefined}
              className="w-full rounded-full bg-candy-ink px-4 py-2.5 font-semibold text-white hover:bg-candy-ink/85 disabled:opacity-60">
              Payer {euros(total)} avec ma cagnotte
            </button>
          )}
        </div>
      )}

      {busy && <PaymentPending text={`Paiement de ${euros(total)} avec votre cagnotte. Ne fermez pas la page.`} />}
      {result?.ok && <Receipt order={result.order} />}
      {result && !result.ok && (
        <p role="status" className="mt-3 rounded-xl bg-red-50 px-3 py-2 text-sm font-medium text-red-700">
          <span aria-hidden="true">✖ </span>
          {result.text}
        </p>
      )}
    </aside>
  );
}

// Reçu affiché après un paiement réussi.
function Receipt({ order }) {
  return (
    <div role="status" className="mt-4 overflow-hidden rounded-xl border border-green-200 bg-green-50 text-sm">
      <div className="flex items-center gap-3 bg-green-600 px-4 py-3 text-white">
        <span aria-hidden="true" className="flex h-8 w-8 items-center justify-center rounded-full bg-white text-lg font-bold text-green-600">✓</span>
        <div>
          <p className="font-bold">Commande payée</p>
          <p className="text-xs text-white/85">Merci pour votre achat !</p>
        </div>
      </div>

      <p className="flex items-baseline justify-between border-b border-dashed border-green-200 px-4 py-3">
        <span className="text-candy-ink/70">Montant</span>
        <span className="text-xl font-bold text-candy-ink">{euros(order.total)}</span>
      </p>

      <dl className="space-y-2 px-4 py-3 text-candy-ink">
        <ReceiptRow label="Commande">
          <span className="rounded bg-white px-1.5 py-0.5 font-mono text-xs">n° {order.id.slice(0, 8)}</span>
        </ReceiptRow>
        <ReceiptRow label="Payé avec">Ma cagnotte</ReceiptRow>
        <ReceiptRow label="Nouveau solde">{euros(order.balance)}</ReceiptRow>
      </dl>
    </div>
  );
}

function ReceiptRow({ label, children }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="shrink-0 text-candy-ink/60">{label}</dt>
      <dd className="text-right font-medium">{children}</dd>
    </div>
  );
}
