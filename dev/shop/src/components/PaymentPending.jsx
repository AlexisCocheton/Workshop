// Fenêtre modale affichée pendant un paiement ou un virement : elle couvre la page,
// ce qui empêche aussi de modifier le panier ou de valider deux fois.
export default function PaymentPending({ title = "Paiement en cours…", text }) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-candy-ink/40 p-4 backdrop-blur-sm">
      <div role="alertdialog" aria-modal="true" aria-labelledby="payment-pending-title" aria-describedby="payment-pending-text"
        className="w-full max-w-xs rounded-2xl bg-white p-6 text-center shadow-xl">
        <span aria-hidden="true"
          className="mx-auto block h-12 w-12 rounded-full border-4 border-candy-light border-t-candy-pink motion-safe:animate-spin" />
        <p id="payment-pending-title" className="mt-4 font-bold">{title}</p>
        <p id="payment-pending-text" className="mt-1 text-sm text-candy-ink/70">{text}</p>
      </div>
    </div>
  );
}

// Durée minimale de la fenêtre : en local l'API répond en quelques millisecondes,
// la fenêtre ne ferait que clignoter.
const MIN_PENDING_MS = 1200;

// Attend l'appel et la durée minimale ; une erreur remonte sans attendre.
export const withMinDelay = (promise) =>
  Promise.all([promise, new Promise((resolve) => setTimeout(resolve, MIN_PENDING_MS))]).then(([result]) => result);
