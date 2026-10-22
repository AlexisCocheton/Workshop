import { useState } from "react";
import { login, register } from "../api.js";

// Connexion ou création de compte client, demandée au moment de payer (ou depuis l'en-tête).
export default function AuthForm({ onLogin, title = "Connectez-vous pour payer" }) {
  const [mode, setMode] = useState("login"); // "login" ou "register"
  const [form, setForm] = useState({ email: "", name: "", password: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const field = (key) => ({ value: form[key], onChange: (e) => setForm({ ...form, [key]: e.target.value }) });
  const input = "mt-1 w-full rounded-lg border border-candy-light px-3 py-2 text-sm";

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const session = mode === "login"
        ? await login(form.email, form.password)
        : await register(form.email, form.name, form.password);
      onLogin(session);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="mt-4 space-y-3 rounded-xl bg-candy-light/50 p-4">
      <p className="text-sm font-semibold">
        {mode === "login" ? title : "Créez votre compte"}
      </p>
      {mode === "register" && (
        <label className="block text-sm">
          Prénom
          <input required className={input} autoComplete="given-name" {...field("name")} />
        </label>
      )}
      <label className="block text-sm">
        E-mail
        <input required type="email" className={input} autoComplete="email" {...field("email")} />
      </label>
      <label className="block text-sm">
        Mot de passe{mode === "register" && " (8 caractères minimum)"}
        <input required type="password" minLength={mode === "register" ? 8 : undefined} className={input}
          autoComplete={mode === "login" ? "current-password" : "new-password"} {...field("password")} />
      </label>
      {error && <p className="text-sm text-red-700">{error}</p>}
      <button disabled={busy} className="w-full rounded-full bg-candy-pink px-4 py-2 font-semibold text-white disabled:opacity-60">
        {mode === "login" ? "Se connecter" : "Créer mon compte"}
      </button>
      <button type="button" className="w-full text-sm text-candy-pink underline"
        onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(null); }}>
        {mode === "login" ? "Pas encore de compte ? Inscrivez-vous" : "Déjà client ? Connectez-vous"}
      </button>
    </form>
  );
}
