import { useState } from "react";
import AuthForm from "./AuthForm.jsx";
import PaymentForm from "./PaymentForm.jsx";
import { euros, placeOrder } from "../api.js";

// Panier et paiement. Le total affiché est indicatif : l'API recalcule avec ses propres prix.
export default function Cart({ products, cart, onQuantity, session, onLogin, onExpired, onOrdered }) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null); // { ok, text }
  const [paying, setPaying] = useState(false); // formulaire de carte affiché

  const lines = products.filter((p) => cart[p.id]).map((p) => ({ ...p, quantity: cart[p.id] }));
  const total = lines.reduce((sum, line) => sum + line.price * line.quantity, 0);

  // payment : résumé renvoyé par PaymentForm (e-mail, adresse, marque, 4 derniers chiffres).
  // L'API ne reçoit que le panier : la carte n'est pas transmise (boutique fictive).
  async function checkout(payment) {
    setBusy(true);
    setResult(null);
    try {
      const order = await placeOrder(session.token, cart);
      setResult({
        ok: true,
        text: `Commande payée : ${euros(order.total)} avec ${payment.brand} •••• ${payment.last4} (n° ${order.id.slice(0, 8)}). Livraison : ${payment.address.street}, ${payment.address.postalCode} ${payment.address.city}. Reçu envoyé à ${payment.email}. Merci !`,
      });
      setPaying(false);
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
              <span className="w-6 text-center">{line.quantity}</span>
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
      {lines.length > 0 && session && !paying && (
        <button
          onClick={() => { setPaying(true); setResult(null); }}
          className="mt-4 w-full rounded-full bg-candy-ink px-4 py-2.5 font-semibold text-white hover:bg-candy-ink/85"
        >
          Payer {euros(total)}
        </button>
      )}
      {lines.length > 0 && session && paying && (
        <PaymentForm amountLabel={euros(total)} busy={busy} onSubmit={checkout} onCancel={() => setPaying(false)} />
      )}

      {result && (
        <p role="status" className={`mt-3 text-sm font-medium ${result.ok ? "text-green-700" : "text-red-700"}`}>
          <span aria-hidden="true">{result.ok ? "✔ " : "✖ "}</span>
          {result.text}
        </p>
      )}
    </aside>
  );
}
