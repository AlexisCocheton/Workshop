import { useState } from "react";
import Card from "./Card.jsx";
import { askAssistant } from "../api.js";

// Assistant RAG des opérateurs (Ollama + LangChain, en local). Lecture seule.
const SUGGESTIONS = [
  "Que faire si le détecteur passe en anomalie ?",
  "Que signifie un taux d'erreurs 5xx élevé ?",
  "Comment vérifier que le service est vraiment rétabli ?",
];

export default function Assistant() {
  const [question, setQuestion] = useState("");
  const [reply, setReply] = useState(null);
  const [busy, setBusy] = useState(false);

  async function ask(text) {
    if (!text.trim() || busy) return;
    setQuestion(text);
    setBusy(true);
    setReply(null);
    try {
      setReply(await askAssistant(text));
    } catch (error) {
      setReply({ answer: `L'assistant est injoignable (${error.message}).`, sources: [] });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Assistant opérateur (IA locale)">
      <form
        className="flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          ask(question);
        }}
      >
        <input
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Posez une question sur une procédure…"
          className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-epsi-ink focus:outline-none"
        />
        <button
          type="submit"
          disabled={busy}
          className="rounded-lg bg-epsi-ink px-4 py-2 text-sm font-semibold text-white hover:bg-epsi-ink/85 disabled:opacity-60"
        >
          Demander
        </button>
      </form>

      <div className="mt-3 flex flex-wrap gap-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            disabled={busy}
            onClick={() => ask(s)}
            className="rounded-full bg-epsi-bg px-3 py-1 text-xs hover:bg-epsi-accent/50 disabled:opacity-60"
          >
            {s}
          </button>
        ))}
      </div>

      {busy && (
        <p className="mt-4 text-sm text-slate-500">
          L'assistant consulte la documentation… (jusqu'à une minute : le modèle tourne en local sur CPU)
        </p>
      )}
      {reply && (
        <div className="mt-4 rounded-lg bg-epsi-bg/60 p-4 text-sm">
          <p className="whitespace-pre-line">{reply.answer}</p>
          {reply.sources?.length > 0 && <p className="mt-2 text-xs text-slate-500">Sources : {reply.sources.join(", ")}</p>}
        </div>
      )}

      <p className="mt-4 text-xs text-slate-500">
        Lecture seule : l'assistant conseille à partir des procédures de l'équipe, il n'agit jamais sur le système.
      </p>
    </Card>
  );
}
