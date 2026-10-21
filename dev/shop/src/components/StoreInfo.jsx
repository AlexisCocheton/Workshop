import { STORE } from "../store.js";

// Coordonnées et horaires de la boutique, avec un lien d'itinéraire (OpenStreetMap).
export default function StoreInfo() {
  const [lat, lon] = STORE.position;
  const directions = `https://www.openstreetmap.org/directions?to=${lat}%2C${lon}#map=17/${lat}/${lon}`;

  return (
    <div className="space-y-4 text-sm">
      <address className="not-italic">
        <p className="font-semibold">Adresse</p>
        <p>{STORE.street}</p>
        <p>{STORE.postalCode} {STORE.city}</p>
        <p className="mt-1">
          <a href={`tel:${STORE.phone.replace(/\s/g, "")}`} className="text-candy-pink underline">{STORE.phone}</a>
        </p>
      </address>

      <div>
        <p className="font-semibold">Horaires</p>
        <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-4 gap-y-0.5">
          {STORE.hours.map(([days, time]) => (
            <div key={days} className="contents">
              <dt>{days}</dt>
              <dd className={time === "Fermé" ? "text-candy-ink/50" : ""}>{time}</dd>
            </div>
          ))}
        </dl>
      </div>

      <p>
        <span aria-hidden="true">🚋 </span>
        {STORE.access}
      </p>

      <a href={directions} target="_blank" rel="noreferrer"
        className="inline-block rounded-full bg-candy-ink px-4 py-2 font-semibold text-white hover:bg-candy-ink/85">
        Itinéraire
      </a>
    </div>
  );
}
