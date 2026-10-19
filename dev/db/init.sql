-- Base de la plateforme de paiement fictive.
-- La table est aussi créée par l'API au démarrage (idempotent) ; ce fichier
-- documente le schéma et permet de l'initialiser sans l'API.

CREATE TABLE IF NOT EXISTS transactions (
    id          TEXT PRIMARY KEY,
    amount      NUMERIC NOT NULL,
    currency    TEXT NOT NULL DEFAULT 'EUR',
    status      TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
