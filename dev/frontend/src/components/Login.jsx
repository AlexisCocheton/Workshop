import { useState } from "react";
import { backofficeLogin, checkFace } from "../api.js";

const INPUT = "mt-1 w-full rounded-lg border border-epsi-ink/20 px-3 py-2 font-normal focus:outline-none focus:ring-2 focus:ring-epsi-accent";
const BUTTON = "w-full rounded-lg bg-epsi-ink px-4 py-2 font-semibold text-white hover:bg-epsi-ink/85 disabled:opacity-60";

// Connexion au back-office (consigne additionnelle 1) : identifiant -> caméra -> mot de passe.
// Attente de 30 s, blocage de 5 min et ticket visage sont appliqués par le service auth :
// cette page ne fait qu'afficher ses réponses, la modifier ne permet pas de les contourner.
export default function Login({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [faceTicket, setFaceTicket] = useState(null); // présent = visage reconnu, étape mot de passe
  const [message, setMessage] = useState(null);
  const [busy, setBusy] = useState(false);

  // Échec : on recommence toute l'identification, identifiant vidé.
  function restart(text) {
    setUsername("");
    setPassword("");
    setFaceTicket(null);
    setMessage(text);
  }

  async function submit(event, request, onResult) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      onResult(await request());
    } catch {
      setMessage("Service d'authentification injoignable.");
    } finally {
      setBusy(false);
    }
  }

  const submitUsername = (event) =>
    submit(event, () => checkFace(username), (result) => {
      if (result.recognized) setFaceTicket(result.face_ticket);
      else if (result.ok) restart(`${result.reason}. Nouvel essai possible dans ${result.retry_in} s.`);
      else setMessage(result.detail); // compte bloqué, caméra indisponible…
    });

  const submitPassword = (event) =>
    submit(event, () => backofficeLogin(username, password, faceTicket), (result) => {
      if (result.ok) onLogin(result.token);
      else restart(result.detail);
    });

  return (
    <main className="flex min-h-screen items-center justify-center bg-epsi-bg px-4 text-epsi-ink">
      <div className="w-full max-w-sm rounded-2xl bg-white p-8 shadow-sm ring-1 ring-epsi-ink/10">
        <p className="text-xs font-semibold uppercase tracking-widest text-epsi-ink/60">Project Resilience-Alpha</p>
        <h1 className="mt-1 text-xl font-bold">Connexion au back-office</h1>

        {message && (
          <p role="alert" className="mt-4 rounded-lg bg-status-critical/10 px-3 py-2 text-sm">
            <span aria-hidden="true" className="text-status-critical">✖ </span>
            {message}
          </p>
        )}

        {faceTicket ? (
          <form onSubmit={submitPassword} className="mt-5 space-y-4">
            <p className="text-sm">
              <span aria-hidden="true" className="text-status-good">✔ </span>
              Visage reconnu : <strong>{username}</strong>
            </p>
            <label className="block text-sm font-semibold">
              Mot de passe
              <input
                type="password"
                autoFocus
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={busy}
                className={INPUT}
              />
            </label>
            <button type="submit" disabled={busy} className={BUTTON}>
              {busy ? "Vérification…" : "Se connecter"}
            </button>
          </form>
        ) : (
          <form onSubmit={submitUsername} className="mt-5 space-y-4">
            <label className="block text-sm font-semibold">
              Identifiant
              <input
                autoFocus
                required
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value.trim())}
                disabled={busy}
                className={INPUT}
              />
            </label>
            <p className="text-xs text-epsi-ink/60">
              Une fenêtre caméra s'ouvre ensuite : placez votre visage dans l'ovale jusqu'à ce qu'il
              devienne vert (15 s maximum).
            </p>
            <button type="submit" disabled={busy} className={BUTTON}>
              {busy ? "Placez votre visage dans l'ovale…" : "Continuer"}
            </button>
          </form>
        )}
      </div>
    </main>
  );
}
