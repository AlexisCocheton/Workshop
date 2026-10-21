import { useState } from "react";
import { updateProfile } from "../api.js";

const input = "mt-1 w-full rounded-lg border border-candy-light px-3 py-2 text-sm";

// Champ texte avec libellé ; "hint" précise le format attendu.
function Field({ label, hint, ...props }) {
  return (
    <label className="block text-sm">
      {label}
      {hint && <span className="text-candy-ink/60"> ({hint})</span>}
      <input className={input} {...props} />
    </label>
  );
}

// Informations personnelles : identité, contact et adresse de livraison.
// profile : { email, name, phone, street, postal_code, city }, tel que renvoyé par l'API.
export default function ProfileForm({ session, profile, onExpired, onSaved }) {
  const [form, setForm] = useState(profile);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null); // { ok, text }

  const field = (key, format = (v) => v) => ({
    value: form[key],
    onChange: (e) => {
      setForm({ ...form, [key]: format(e.target.value) });
      setResult(null);
    },
  });
  const changed = Object.keys(profile).some((key) => form[key] !== profile[key]);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setResult(null);
    try {
      const saved = await updateProfile(session.token, form);
      setForm(saved);
      onSaved(saved);
      setResult({ ok: true, text: "Profil enregistré." });
    } catch (e) {
      if (e.status === 401) onExpired();
      setResult({ ok: false, text: e.message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-5 rounded-2xl bg-white p-5 shadow-sm">
      <fieldset className="space-y-3">
        <legend className="font-semibold">Informations personnelles</legend>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Prénom" required autoComplete="given-name" {...field("name")} />
          <Field label="Téléphone" hint="facultatif" type="tel" autoComplete="tel" placeholder="06 12 34 56 78"
            {...field("phone", (v) => v.replace(/[^\d+ ]/g, "").slice(0, 20))} />
        </div>
        <Field label="E-mail" hint="sert aussi à la connexion" type="email" required autoComplete="email"
          {...field("email")} />
      </fieldset>

      <fieldset className="space-y-3">
        <legend className="font-semibold">Adresse de livraison</legend>
        <Field label="Numéro et rue" autoComplete="shipping street-address" placeholder="12 rue des Bonbons"
          {...field("street")} />
        <div className="grid grid-cols-[7rem_1fr] gap-3">
          <Field label="Code postal" inputMode="numeric" pattern="\d{5}" title="5 chiffres" placeholder="75001"
            autoComplete="shipping postal-code" {...field("postal_code", (v) => v.replace(/\D/g, "").slice(0, 5))} />
          <Field label="Ville" autoComplete="shipping address-level2" {...field("city")} />
        </div>
      </fieldset>

      <div className="flex flex-wrap items-center gap-3">
        <button disabled={busy || !changed}
          className="rounded-full bg-candy-pink px-5 py-2 font-semibold text-white disabled:opacity-50">
          {busy ? "Enregistrement…" : "Enregistrer"}
        </button>
        {changed && !busy && (
          <button type="button" className="text-sm text-candy-pink underline"
            onClick={() => { setForm(profile); setResult(null); }}>
            Annuler les modifications
          </button>
        )}
        {result && (
          <p role="status" className={`text-sm font-medium ${result.ok ? "text-green-700" : "text-red-700"}`}>
            <span aria-hidden="true">{result.ok ? "✔ " : "✖ "}</span>
            {result.text}
          </p>
        )}
      </div>
    </form>
  );
}
