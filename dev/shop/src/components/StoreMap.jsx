import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { SHOP_NAME } from "./Header.jsx";
import { STORE } from "../store.js";

// Marqueur en HTML (emoji) plutôt que l'icône PNG de Leaflet, que Vite ne
// retrouve pas sans configuration supplémentaire.
const candyIcon = L.divIcon({
  className: "",
  html: '<div style="font-size:30px;line-height:1;filter:drop-shadow(0 2px 2px rgb(0 0 0 / .35))">🍬</div>',
  iconSize: [30, 30],
  iconAnchor: [15, 15],
  popupAnchor: [0, -16],
});

// Mini-carte OpenStreetMap (Leaflet, gratuite et sans clé d'API) centrée sur la boutique.
// La molette ne zoome pas, pour ne pas piéger le défilement de la page.
export default function StoreMap({ className = "h-72" }) {
  return (
    <MapContainer center={STORE.position} zoom={16} scrollWheelZoom={false}
      className={`z-0 w-full rounded-2xl ${className}`}>
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
      />
      <Marker position={STORE.position} icon={candyIcon}>
        <Popup>
          <strong>{SHOP_NAME}</strong>
          <br />
          {STORE.street}, {STORE.postalCode} {STORE.city}
        </Popup>
      </Marker>
    </MapContainer>
  );
}
