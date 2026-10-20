// Appels aux services de la plateforme.
// Adresses configurables par variables VITE_* (fichier .env du frontend) pour
// s'adapter aux ports réels de la machine ; valeurs par défaut = compose.yml.
export const WAF = import.meta.env.VITE_WAF_URL || "http://localhost:8080";
export const DETECTOR = import.meta.env.VITE_DETECTOR_URL || "http://localhost:8000";
export const REMEDIATION = import.meta.env.VITE_REMEDIATION_URL || "http://localhost:8200";
export const ASSISTANT = import.meta.env.VITE_ASSISTANT_URL || "http://localhost:8001";

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

export const askAssistant = (question) =>
  getJson(`${ASSISTANT}/ask`, { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ question }) });
