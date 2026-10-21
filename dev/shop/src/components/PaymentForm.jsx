import { useState } from "react";
import Cards from "react-credit-cards-2";
import "react-credit-cards-2/dist/es/styles-compiled.css";
import valid from "card-validator";

// Saisie des informations de paiement au moment de l'achat.
// - react-credit-cards-2 : aperçu visuel de la carte (marque détectée, retournement sur le CVC).
// - card-validator (Braintree) : contrôle du numéro (Luhn), de la date d'expiration et du CVC.
// Les données de carte restent en mémoire, le temps du paiement : jamais dans localStorage,
// et le CVC n'est jamais conservé (interdit par PCI-DSS). Seul un résumé masqué remonte.
const EMPTY = { email: "", street: "", postalCode: "", city: "", name: "", number: "", expiry: "", cvc: "" };
const ADDRESS_FIELDS = ["street", "postalCode", "city"];

// Formatage à la frappe : groupes de chiffres selon la marque, "MM/AA" pour la date.
function formatNumber(value) {
  const digits = value.replace(/\D/g, "").slice(0, 19);
  const card = valid.number(digits).card;
  const gaps = card?.gaps ?? [4, 8, 12, 16];
  return digits.split("").reduce((out, digit, i) => out + (gaps.includes(i) ? " " : "") + digit, "");
}
function formatExpiry(value) {
  const digits = value.replace(/\D/g, "").slice(0, 4);
  return digits.length > 2 ? `${digits.slice(0, 2)}/${digits.slice(2)}` : digits;
}

function validate(form) {
  const number = valid.number(form.number);
  const cvcSize = number.card?.code.size ?? 3;
  return {
    email: /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email) ? null : "Adresse e-mail invalide.",
    street: form.street.trim().length >= 5 ? null : "Adresse de livraison requise.",
    postalCode: /^\d{5}$/.test(form.postalCode) ? null : "Code postal à 5 chiffres.",
    city: form.city.trim() ? null : "Ville requise.",
    name: valid.cardholderName(form.name).isValid ? null : "Nom du titulaire requis.",
    number: number.isValid ? null : "Numéro de carte invalide.",
    expiry: valid.expirationDate(form.expiry).isValid ? null : "Date d'expiration invalide ou dépassée.",
    cvc: valid.cvv(form.cvc, cvcSize).isValid ? null : `Code de sécurité à ${cvcSize} chiffres.`,
  };
}

export default function PaymentForm({ amountLabel, busy, onSubmit, onCancel }) {
  const [form, setForm] = useState(EMPTY);
  const [focused, setFocused] = useState("");
  const [touched, setTouched] = useState({});

  const errors = validate(form);
  const isValid = Object.values(errors).every((error) => !error);
  const cvcSize = valid.number(form.number).card?.code.size ?? 3;

  const input = "mt-1 w-full rounded-lg border border-candy-light px-3 py-2 text-sm";
  const field = (key, format = (v) => v) => ({
    name: key,
    value: form[key],
    onChange: (e) => setForm({ ...form, [key]: format(e.target.value) }),
    onFocus: () => setFocused(key === "email" || ADDRESS_FIELDS.includes(key) ? "" : key),
    onBlur: () => setTouched({ ...touched, [key]: true }),
    "aria-invalid": Boolean(touched[key] && errors[key]),
  });
  const error = (key) =>
    touched[key] && errors[key] && <span className="mt-1 block text-xs text-red-700">{errors[key]}</span>;

  function submit(event) {
    event.preventDefault();
    setTouched(Object.fromEntries(Object.keys(EMPTY).map((key) => [key, true])));
    if (!isValid) return;
    const digits = form.number.replace(/\D/g, "");
    // Résumé non sensible : de quoi afficher « Visa •••• 4242 » sur un reçu, rien de plus.
    onSubmit({
      email: form.email,
      address: { street: form.street.trim(), postalCode: form.postalCode, city: form.city.trim() },
      cardholder: form.name,
      brand: valid.number(digits).card?.niceType ?? "Carte",
      last4: digits.slice(-4),
      expiry: form.expiry,
    });
    // Efface numéro, date et CVC ; garde e-mail, adresse et titulaire pour une prochaine commande.
    setForm({ ...EMPTY, email: form.email, street: form.street, postalCode: form.postalCode, city: form.city, name: form.name });
  }

  return (
    // Hauteur bornée et défilement interne : le panier est "sticky" sur grand écran,
    // sans cela le bas du formulaire (bouton Payer) sortirait de l'écran.
    <form onSubmit={submit} noValidate
      className="mt-4 max-h-[70vh] space-y-3 overflow-y-auto overscroll-contain rounded-xl bg-candy-light/50 p-4">
      <p className="text-sm font-semibold">Informations de paiement</p>

      <div className="origin-top scale-[0.85]">
        <Cards
          number={form.number}
          name={form.name}
          expiry={form.expiry.replace("/", "")}
          cvc={form.cvc}
          focused={focused}
          placeholders={{ name: "NOM PRÉNOM" }}
          locale={{ valid: "expire fin" }}
        />
      </div>

      <label className="block text-sm">
        E-mail (pour le reçu)
        <input type="email" className={input} autoComplete="email" {...field("email")} />
        {error("email")}
      </label>

      <fieldset className="space-y-3">
        <legend className="text-sm font-semibold">Adresse de livraison</legend>
        <label className="block text-sm">
          Numéro et rue
          <input className={input} autoComplete="shipping street-address" placeholder="12 rue des Bonbons"
            {...field("street")} />
          {error("street")}
        </label>
        <div className="grid grid-cols-[7rem_1fr] gap-3">
          <label className="block text-sm">
            Code postal
            <input className={input} inputMode="numeric" autoComplete="shipping postal-code" placeholder="75001"
              {...field("postalCode", (v) => v.replace(/\D/g, "").slice(0, 5))} />
            {error("postalCode")}
          </label>
          <label className="block text-sm">
            Ville
            <input className={input} autoComplete="shipping address-level2" {...field("city")} />
            {error("city")}
          </label>
        </div>
      </fieldset>

      <p className="text-sm font-semibold">Carte bancaire</p>
      <label className="block text-sm">
        Titulaire de la carte
        <input className={input} autoComplete="cc-name" {...field("name")} />
        {error("name")}
      </label>
      <label className="block text-sm">
        Numéro de carte
        <input className={input} inputMode="numeric" autoComplete="cc-number" placeholder="1234 5678 9012 3456"
          {...field("number", formatNumber)} />
        {error("number")}
      </label>
      <div className="grid grid-cols-2 gap-3">
        <label className="block text-sm">
          Expiration
          <input className={input} inputMode="numeric" autoComplete="cc-exp" placeholder="MM/AA"
            {...field("expiry", formatExpiry)} />
          {error("expiry")}
        </label>
        <label className="block text-sm">
          Code (CVC)
          <input type="password" className={input} inputMode="numeric" autoComplete="cc-csc"
            placeholder={"•".repeat(cvcSize)} {...field("cvc", (v) => v.replace(/\D/g, "").slice(0, cvcSize))} />
          {error("cvc")}
        </label>
      </div>

      <button disabled={busy}
        className="w-full rounded-full bg-candy-ink px-4 py-2.5 font-semibold text-white hover:bg-candy-ink/85 disabled:opacity-60">
        {busy ? "Paiement en cours…" : `Payer ${amountLabel}`}
      </button>
      <button type="button" className="w-full text-sm text-candy-pink underline" onClick={onCancel}>
        Annuler
      </button>
      <p className="text-xs text-candy-ink/60">
        🔒 Boutique fictive : utilisez une carte de test (ex. 4242 4242 4242 4242). Rien n'est débité ni conservé.
      </p>
    </form>
  );
}
