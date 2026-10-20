// Appels aux services de la plateforme.
// Par défaut, on joint les services sur la même adresse que celle qui a servi
// le dashboard (ouvrir http://127.0.0.1:3000 sur le PC Hôte). On évite
// "localhost" en dur : sous Windows + Docker Desktop, il peut partir en IPv6
// vers le relais WSL et rester bloqué indéfiniment (constaté).
// Adresses surchargeables par variables VITE_* (fichier .env du frontend).
const HOST = window.location.hostname;
export const WAF = import.meta.env.VITE_WAF_URL || `http://${HOST}:8080`;
export const DETECTOR = import.meta.env.VITE_DETECTOR_URL || `http://${HOST}:8000`;
export const REMEDIATION = import.meta.env.VITE_REMEDIATION_URL || `http://${HOST}:8200`;
export const ASSISTANT = import.meta.env.VITE_ASSISTANT_URL || `http://${HOST}:8001`;

// Compte de démonstration public (voir .env.example) : il ne peut que créer
// des transactions fictives.
const DEMO_ACCOUNT = { user: "app", password: "app" };
const JSON_HEADERS = { "Content-Type": "application/json" };

async function getJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

export const fetchStatus = () => getJson(`${DETECTOR}/status`);
export const fetchEvents = () => getJson(`${REMEDIATION}/events`);
export const fetchTransactions = () => getJson(`${WAF}/transactions`);

export async function payDemo() {
  const { token } = await getJson(`${WAF}/auth/login`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(DEMO_ACCOUNT),
  });
  return getJson(`${WAF}/transactions`, {
    method: "POST",
    headers: { ...JSON_HEADERS, Authorization: `Bearer ${token}` },
    body: JSON.stringify({ amount: 42.5, currency: "EUR" }),
  });
}

// Back-office : connexion en deux étapes (visage puis mot de passe), via le WAF.
// On renvoie aussi le code HTTP : un refus (401, 429, 503) porte un message à afficher.
async function postAuth(path, body) {
  const response = await fetch(`${WAF}/auth${path}`, { method: "POST", headers: JSON_HEADERS, body: JSON.stringify(body) });
  return { ok: response.ok, ...(await response.json()) };
}
export const checkFace = (username) => postAuth("/backoffice/face", { username });
export const backofficeLogin = (user, password, faceTicket) =>
  postAuth("/backoffice/login", { user, password, face_ticket: faceTicket });

export const askAssistant = (question) =>
  getJson(`${ASSISTANT}/ask`, { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ question }) });
