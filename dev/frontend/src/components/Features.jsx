import Card from "./Card.jsx";
import { FEATURE_LABELS } from "../status.js";

// Explication de l'alerte : les indicateurs les plus éloignés du trafic normal
// appris par le modèle, en nombre d'écarts-types (z-score).
const UNUSUAL_Z = 3;

export default function Features({ status }) {
  const features = status?.top_features ?? [];

  return (
    <Card title="Pourquoi ? Les indicateurs les plus inhabituels">
      {features.length === 0 ? (
        <p className="text-sm text-slate-500">En attente de mesures…</p>
      ) : (
        <ul className="space-y-3">
          {features.map((f) => (
            <li key={f.name}>
              <div className="flex justify-between gap-3 text-sm">
                <span>{FEATURE_LABELS[f.name] ?? f.name}</span>
                <span className="font-semibold">
                  {Number(f.value).toFixed(2)} · z = {f.zscore}
                  {Math.abs(f.zscore) >= UNUSUAL_Z && " ⚠ inhabituel"}
                </span>
              </div>
              <div className="mt-1 h-2 rounded-full bg-slate-100">
                <div className="h-2 rounded-full bg-[#2a78d6]" style={{ width: `${Math.min(Math.abs(f.zscore), 10) * 10}%` }} />
              </div>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-4 text-xs text-slate-500">
        z = écart à la moyenne du trafic normal, en écarts-types. Au-delà de {UNUSUAL_Z}, la valeur est inhabituelle.
      </p>
    </Card>
  );
}
