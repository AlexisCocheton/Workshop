import { useState } from "react";
import { changePassword } from "../api.js";

const EMPTY = { current: "", next: "", confirm: "" };

// Changement de mot de passe : l'API exige l'ancien, en plus du jeton de session.
export default function PasswordForm({ session, onExpired }) {
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null); // { ok, text }

  const input = "mt-1 w-full rounded-lg border border-candy-light px-3 py-2 text-sm";
  const field = (key) => ({ value: form[key], onChange: (e) => setForm({ ...form, [key]: e.target.value }) });
  const mismatch = form.confirm !== "" && form.next !== form.confirm;

  async function submit(event) {
    event.preventDefault();
    if (mismatch) return;
    setBusy(true);
    setResult(null);
    try {
      await changePassword(session.token, form.current, form.next);
      setForm(EMPTY);
      setResult({ ok: true, text: "Mot de passe modifié." });
    } catch (e) {
      if (e.status === 401) onExpired();
      setResult({ ok: false, text: e.message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3 rounded-2xl bg-white p-5 shadow-sm">
      <p className="font-semibold">Mot de passe</p>
      <label className="block text-sm">
        Mot de passe actuel
        <input required type="password" className={input} autoComplete="current-password" {...field("current")} />
      </label>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-sm">
          Nouveau mot de passe
          <input required type="password" minLength={8} className={input} autoComplete="new-password" {...field("next")} />
          <span className="mt-1 block text-xs text-candy-ink/60">8 caractères minimum.</span>
        </label>
        <label className="block text-sm">
          Confirmation
          <input required type="password" className={input} autoComplete="new-password" aria-invalid={mismatch}
            {...field("confirm")} />
          {mismatch && <span className="mt-1 block text-xs text-red-700">Les deux mots de passe diffèrent.</span>}
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <button disabled={busy || mismatch}
          className="rounded-full bg-candy-ink px-5 py-2 font-semibold text-white disabled:opacity-50">
          {busy ? "Modification…" : "Changer le mot de passe"}
        </button>
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
