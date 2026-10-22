"""API de paiement fictive (pôle Dev).

Traite des transactions fictives, les persiste en base, et expose des
métriques Prometheus (lues par le détecteur IA).

Sert aussi la boutique de confiseries (routes /shop/*, site dev/shop/) :
catalogue, comptes clients, commandes et historique. Chaque commande payée
crée une transaction : la boutique passe par le même chemin que l'incident.

Contient volontairement une faille de démonstration (voir /pay/callback) :
elle met le service hors d'usage. C'est ce que l'attaque exploite ; seul un
redémarrage du conteneur (déclenché par le moteur de remédiation) le rétablit.
Aucune donnée réelle : tout est fictif.
"""
import base64
import binascii
import hashlib
import hmac
import os
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import jwt
import psycopg
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel
from starlette.responses import Response

# Le secret JWT est obligatoire : sans lui, n'importe qui pourrait forger un
# jeton valide. On refuse de démarrer plutôt que d'utiliser un secret par défaut.
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET est obligatoire.")
DB_DSN = os.getenv("DB_DSN", "postgresql://app:app@db:5432/payments")
# Compte marchand de la boutique (réapprovisionne le stock, ajoute des confiseries).
# Créé au démarrage, jamais par inscription : personne ne peut se déclarer marchand.
# Sans ces deux variables, il n'y a pas de compte marchand.
MERCHANT_EMAIL = os.getenv("SHOP_MERCHANT_EMAIL", "").strip().lower()
MERCHANT_PASSWORD = os.getenv("SHOP_MERCHANT_PASSWORD", "")

# Origines autorisées (CORS) : le dashboard et la boutique, au lieu de tout ouvrir.
ALLOWED_ORIGINS = (
    os.getenv("DASHBOARD_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    + os.getenv("SHOP_ORIGINS", "http://localhost:3002,http://127.0.0.1:3002").split(",")
)

# Métriques exposées sur /metrics. Les noms correspondent à ce que lit le
# détecteur IA (ai/detector/features.py) : ne pas les renommer sans prévenir.
REQUESTS = Counter("http_requests_total", "Requêtes HTTP traitées", ["method", "status"])
LATENCY = Histogram("http_request_duration_seconds", "Durée des requêtes", ["handler"])

# État en mémoire : remis à zéro à chaque redémarrage du conteneur.
state = {"broken": False}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="API de paiement", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_methods=["*"], allow_headers=["*"])
bearer = HTTPBearer()


@app.middleware("http")
async def record_metrics(request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    REQUESTS.labels(request.method, str(response.status_code)).inc()
    LATENCY.labels(request.url.path).observe(time.perf_counter() - start)
    return response


def connect() -> psycopg.Connection:
    return psycopg.connect(DB_DSN, autocommit=True)


# Schéma de la base, identique à dev/db/init.sql. Rejoué à chaque démarrage
# (IF NOT EXISTS) : un volume existant, sur lequel init.sql ne s'exécute plus,
# reçoit quand même les nouvelles tables.
SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY, amount NUMERIC NOT NULL, currency TEXT NOT NULL DEFAULT 'EUR',
    status TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL,
    price NUMERIC(8, 2) NOT NULL, stock INTEGER NOT NULL CHECK (stock >= 0), emoji TEXT NOT NULL);
ALTER TABLE products ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE products ADD COLUMN IF NOT EXISTS image BYTEA;
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
    password_hash TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
ALTER TABLE customers ADD COLUMN IF NOT EXISTS phone TEXT NOT NULL DEFAULT '';
ALTER TABLE customers ADD COLUMN IF NOT EXISTS street TEXT NOT NULL DEFAULT '';
ALTER TABLE customers ADD COLUMN IF NOT EXISTS postal_code TEXT NOT NULL DEFAULT '';
ALTER TABLE customers ADD COLUMN IF NOT EXISTS city TEXT NOT NULL DEFAULT '';
ALTER TABLE customers ADD COLUMN IF NOT EXISTS is_merchant BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS balance NUMERIC(10, 2) NOT NULL DEFAULT 0 CHECK (balance >= 0);
CREATE TABLE IF NOT EXISTS wallet_movements (
    id SERIAL PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id),
    kind TEXT NOT NULL, amount NUMERIC(10, 2) NOT NULL, label TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id),
    transaction_id TEXT NOT NULL REFERENCES transactions(id), total NUMERIC(10, 2) NOT NULL,
    status TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS order_items (
    order_id TEXT NOT NULL REFERENCES orders(id), product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0), unit_price NUMERIC(8, 2) NOT NULL,
    PRIMARY KEY (order_id, product_id));
"""

# Catalogue de départ (fictif), inséré seulement si la table des produits est vide.
# L'ordre fixe les id (1, 2, …), donc les photos dev/shop/public/products/<id>.jpg.
PRODUCTS = [
    ("Fraises Tagada", "Guimauves roses à la fraise, sachet de 200 g.", 2.50, 120, "🍓"),
    ("Oursons guimauve", "Oursons enrobés de chocolat au lait, boîte de 10.", 4.90, 60, "🧸"),
    ("Sucettes arc-en-ciel", "Grande sucette tourbillon aux fruits.", 1.80, 200, "🍭"),
    ("Caramels au beurre salé", "Caramels tendres, sachet de 150 g.", 5.20, 80, "🍬"),
    ("Dragibus", "Bonbons gélifiés multicolores, sachet de 250 g.", 2.90, 150, "🌈"),
    ("Chocolats pralinés", "Assortiment de pralinés noisette, boîte de 12.", 9.90, 40, "🍫"),
    ("Réglisse", "Rouleaux de réglisse, sachet de 100 g.", 2.20, 90, "🌀"),
    ("Berlingots", "Berlingots aux fruits, bocal de 200 g.", 6.50, 50, "💎"),
    ("Chamallows", "Grosses guimauves à griller, sachet de 300 g.", 3.40, 100, "☁️"),
    ("Bonbons acidulés", "Bonbons qui piquent, sachet de 200 g.", 2.70, 130, "🍋"),
]


def init_db():
    """Crée les tables au démarrage, en réessayant tant que la base n'est pas prête."""
    for _ in range(15):
        try:
            with connect() as conn:
                conn.execute(SCHEMA)
                if conn.execute("SELECT count(*) FROM products").fetchone()[0] == 0:
                    for product in PRODUCTS:
                        conn.execute(
                            "INSERT INTO products (name, description, price, stock, emoji) "
                            "VALUES (%s, %s, %s, %s, %s)",
                            product,
                        )
                create_merchant(conn)
            return
        except psycopg.OperationalError:
            time.sleep(2)


def create_merchant(conn: psycopg.Connection):
    """Crée le compte marchand défini dans .env, ou lui redonne son rôle et son mot de passe.
    Un seul marchand : les comptes créés avec une ancienne valeur de .env perdent le rôle
    (sinon ils gardent l'accès à l'espace marchand, et une épargne qui ne reçoit rien)."""
    conn.execute("UPDATE customers SET is_merchant = false WHERE is_merchant AND email <> %s", (MERCHANT_EMAIL,))
    if not (MERCHANT_EMAIL and MERCHANT_PASSWORD):
        return
    if len(MERCHANT_PASSWORD) < 8:
        print("[api] SHOP_MERCHANT_PASSWORD trop court (8 caractères minimum) : pas de compte marchand", flush=True)
        return
    conn.execute(
        "INSERT INTO customers (email, name, password_hash, is_merchant) VALUES (%s, 'Marchand', %s, true) "
        "ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash, is_merchant = true",
        (MERCHANT_EMAIL, hash_password(MERCHANT_PASSWORD)),
    )


# Jetons admis sur les routes paiement : l'opérateur du back-office (aud
# « backoffice ») et le compte de service du simulateur de trafic (sans audience).
# On exclut ainsi un jeton client (aud « customer ») ou un ticket visage (« face »),
# qui n'ont pas à lire les paiements.
PAYMENT_AUDIENCES = {None, "backoffice"}


def require_token(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    try:
        # verify_aud=False : on décode d'abord, puis on contrôle l'audience nous-mêmes
        # (PyJWT, sans audience attendue, refuserait tout jeton qui en porte une).
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"],
                             options={"verify_aud": False})
    except jwt.InvalidTokenError:
        raise HTTPException(401, "jeton invalide")
    if payload.get("aud") not in PAYMENT_AUDIENCES:
        raise HTTPException(403, "ce jeton n'autorise pas l'accès aux paiements")


class TransactionIn(BaseModel):
    amount: float
    currency: str = "EUR"


@app.get("/healthz")
def healthz():
    if state["broken"]:
        raise HTTPException(503, "service dégradé")
    return {"status": "ok"}


@app.post("/transactions")
def create_transaction(tx: TransactionIn, _=Depends(require_token)):
    if state["broken"]:
        raise HTTPException(500, "erreur interne du service de paiement")
    row = {"id": str(uuid.uuid4()), "amount": tx.amount, "currency": tx.currency, "status": "accepted"}
    with connect() as conn:
        conn.execute(
            "INSERT INTO transactions (id, amount, currency, status) "
            "VALUES (%(id)s, %(amount)s, %(currency)s, %(status)s)",
            row,
        )
    return row


@app.get("/transactions")
def list_transactions(_=Depends(require_token)):
    # LEFT JOIN sur orders : une transaction née d'un achat boutique y est liée
    # (orders.transaction_id), une transaction fictive du dashboard ne l'est pas.
    # On en déduit la provenance et, pour un achat, le nombre d'articles commandés.
    with connect() as conn:
        rows = conn.execute(
            "SELECT t.id, t.amount, t.currency, t.status, t.created_at, o.id, "
            "       (SELECT COALESCE(SUM(quantity), 0) FROM order_items WHERE order_id = o.id) "
            "FROM transactions t LEFT JOIN orders o ON o.transaction_id = t.id "
            "ORDER BY t.created_at DESC LIMIT 20"
        ).fetchall()
    return [
        {
            "id": r[0], "amount": float(r[1]), "currency": r[2], "status": r[3],
            "created_at": r[4].isoformat(),
            # Provenance visible pour l'opérateur : achat client (boutique) ou test (dashboard).
            "source": "boutique" if r[5] else "fictive",
            "order_id": r[5],
            "items": int(r[6]) if r[5] else None,
        }
        for r in rows
    ]


@app.get("/orders")
def list_shop_orders(_=Depends(require_token)):
    """Vrais achats boutique, pour le back-office : articles, total, date, statut.

    Réservé à un porteur de jeton valide (le dashboard envoie son jeton
    back-office) : lire les paiements est une action métier, pas une donnée
    publique (OWASP A01). On n'expose en plus aucune donnée nominative du
    client : la supervision n'en a pas besoin (sujet §5)."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT o.id, o.total, o.status, o.created_at, p.name, p.emoji, i.quantity, i.unit_price "
            "FROM orders o JOIN order_items i ON i.order_id = o.id JOIN products p ON p.id = i.product_id "
            "ORDER BY o.created_at DESC, o.id DESC, p.name LIMIT 100"
        ).fetchall()
    orders = {}  # regroupe les lignes par commande, la plus récente d'abord
    for order_id, total, status, created_at, name, emoji, quantity, unit_price in rows:
        order = orders.setdefault(order_id, {
            "id": order_id, "total": float(total), "status": status,
            "created_at": created_at.isoformat(), "items": [],
        })
        order["items"].append({"name": name, "emoji": emoji, "quantity": quantity, "unit_price": float(unit_price)})
    return list(orders.values())


@app.post("/pay/callback")
def payment_callback(payload: dict):
    """FAILLE DE DÉMONSTRATION (laboratoire uniquement).

    Callback de paiement non authentifié : un payload malformé met le service
    hors d'usage (toutes les transactions suivantes échouent). Représente
    l'exploitation d'une vulnérabilité applicative. Le WAF ne bloque pas ce
    chemin : c'est à la détection ML + remédiation de rattraper l'incident.
    """
    if payload.get("status") == "__CRASH__":
        state["broken"] = True
    return {"received": True}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# --- Boutique de confiseries (site dev/shop/) ---------------------------------


def hash_password(password: str, salt: bytes | None = None) -> str:
    """Hachage scrypt salé (bibliothèque standard) : jamais de mot de passe en clair en base."""
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"{salt.hex()}${digest.hex()}"


def password_matches(password: str, stored: str) -> bool:
    salt = bytes.fromhex(stored.split("$")[0])
    # compare_digest : comparaison à temps constant
    return hmac.compare_digest(hash_password(password, salt), stored)


def customer_token(customer_id: int) -> str:
    """Jeton client. L'audience « customer » l'empêche de servir sur /transactions
    (qui n'attend pas d'audience) ou au back-office (audience « backoffice »)."""
    payload = {
        "sub": str(customer_id),
        "aud": "customer",
        "exp": datetime.now(timezone.utc) + timedelta(hours=8),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def require_customer(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> int:
    """Renvoie l'id du client connecté."""
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"], audience="customer")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "session expirée, reconnectez-vous")
    return int(payload["sub"])


class RegisterIn(BaseModel):
    email: str
    name: str
    password: str


class LoginIn(BaseModel):
    email: str
    password: str


class ProfileIn(BaseModel):
    email: str
    name: str
    phone: str = ""
    street: str = ""
    postal_code: str = ""
    city: str = ""


class PasswordIn(BaseModel):
    current_password: str
    new_password: str


class OrderItemIn(BaseModel):
    product_id: int
    quantity: int


class OrderIn(BaseModel):
    items: list[OrderItemIn]


class TopUpIn(BaseModel):
    amount: float


class PayoutIn(BaseModel):
    amount: float
    iban: str
    holder: str


class RestockIn(BaseModel):
    quantity: int


class ProductIn(BaseModel):
    name: str
    description: str
    price: float
    stock: int
    emoji: str = "🍬"
    image: str | None = None  # JPEG en base64, réduit par le navigateur (le WAF borne le corps à 64 Ko)


# L'image n'est pas lue avec le catalogue : seul un indicateur indique qu'elle existe.
PRODUCT_COLUMNS = "id, name, description, price, stock, emoji, image IS NOT NULL"
MAX_IMAGE = 48_000  # octets, une fois décodée


def product_dict(r) -> dict:
    return {"id": r[0], "name": r[1], "description": r[2], "price": float(r[3]), "stock": r[4], "emoji": r[5],
            "has_image": r[6]}


def decode_image(data: str | None) -> bytes | None:
    """Décode l'image envoyée par le marchand. Seul le JPEG est accepté, vérifié à sa
    signature et non au type annoncé : on ne sert jamais un fichier arbitraire."""
    if not data:
        return None
    try:
        image = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(422, "image illisible")
    if len(image) > MAX_IMAGE:
        raise HTTPException(422, f"image trop lourde ({MAX_IMAGE // 1000} Ko maximum)")
    if not image.startswith(b"\xff\xd8\xff"):
        raise HTTPException(422, "image JPEG attendue")
    return image


@app.get("/shop/products")
def list_products():
    with connect() as conn:
        rows = conn.execute(f"SELECT {PRODUCT_COLUMNS} FROM products WHERE NOT archived ORDER BY id").fetchall()
    return [product_dict(r) for r in rows]


@app.get("/shop/products/{product_id}/image")
def product_image(product_id: int):
    with connect() as conn:
        row = conn.execute("SELECT image FROM products WHERE id = %s AND image IS NOT NULL", (product_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "pas d'image")
    return Response(bytes(row[0]), media_type="image/jpeg", headers={"Cache-Control": "public, max-age=3600"})


@app.post("/shop/register")
def register(body: RegisterIn):
    email, name = body.email.strip().lower(), body.name.strip()
    if "@" not in email or not name:
        raise HTTPException(422, "e-mail ou nom invalide")
    if len(body.password) < 8:
        raise HTTPException(422, "le mot de passe doit faire au moins 8 caractères")
    try:
        with connect() as conn:
            customer_id = conn.execute(
                "INSERT INTO customers (email, name, password_hash) VALUES (%s, %s, %s) RETURNING id",
                (email, name, hash_password(body.password)),
            ).fetchone()[0]
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, "un compte existe déjà avec cet e-mail")
    return {"token": customer_token(customer_id), "name": name, "merchant": False}


@app.post("/shop/login")
def shop_login(body: LoginIn):
    with connect() as conn:
        row = conn.execute(
            "SELECT id, name, password_hash, is_merchant FROM customers WHERE email = %s",
            (body.email.strip().lower(),),
        ).fetchone()
    # Même message que l'e-mail existe ou non : ne révèle pas quels comptes existent.
    if row is None or not password_matches(body.password, row[2]):
        raise HTTPException(401, "e-mail ou mot de passe incorrect")
    return {"token": customer_token(row[0]), "name": row[1], "merchant": row[3]}


PROFILE_COLUMNS = ("email", "name", "phone", "street", "postal_code", "city")


def read_profile(conn: psycopg.Connection, customer_id: int) -> dict:
    row = conn.execute(
        f"SELECT {', '.join(PROFILE_COLUMNS)} FROM customers WHERE id = %s", (customer_id,)
    ).fetchone()
    if row is None:  # compte supprimé depuis l'émission du jeton
        raise HTTPException(401, "session expirée, reconnectez-vous")
    return dict(zip(PROFILE_COLUMNS, row))


@app.get("/shop/profile")
def get_profile(customer_id: int = Depends(require_customer)):
    """Informations personnelles du client connecté (jamais le mot de passe)."""
    with connect() as conn:
        return read_profile(conn, customer_id)


@app.put("/shop/profile")
def update_profile(body: ProfileIn, customer_id: int = Depends(require_customer)):
    profile = {key: getattr(body, key).strip() for key in PROFILE_COLUMNS}
    profile["email"] = profile["email"].lower()
    if "@" not in profile["email"] or not profile["name"]:
        raise HTTPException(422, "e-mail ou nom invalide")
    if profile["postal_code"] and not (profile["postal_code"].isdigit() and len(profile["postal_code"]) == 5):
        raise HTTPException(422, "le code postal doit faire 5 chiffres")
    if any(len(value) > 200 for value in profile.values()):
        raise HTTPException(422, "champ trop long (200 caractères maximum)")
    try:
        with connect() as conn:
            conn.execute(
                f"UPDATE customers SET {', '.join(f'{key} = %s' for key in PROFILE_COLUMNS)} WHERE id = %s",
                (*profile.values(), customer_id),
            )
            return read_profile(conn, customer_id)
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, "un compte existe déjà avec cet e-mail")


@app.put("/shop/profile/password")
def change_password(body: PasswordIn, customer_id: int = Depends(require_customer)):
    """Changement de mot de passe : l'ancien est exigé, un jeton volé ne suffit pas."""
    if len(body.new_password) < 8:
        raise HTTPException(422, "le mot de passe doit faire au moins 8 caractères")
    with connect() as conn:
        row = conn.execute("SELECT password_hash FROM customers WHERE id = %s", (customer_id,)).fetchone()
        if row is None or not password_matches(body.current_password, row[0]):
            raise HTTPException(403, "mot de passe actuel incorrect")
        conn.execute(
            "UPDATE customers SET password_hash = %s WHERE id = %s", (hash_password(body.new_password), customer_id)
        )
    return {"ok": True}


# --- Cagnotte ------------------------------------------------------------------
# Chaque compte a un solde (customers.balance, jamais négatif) et un journal des
# mouvements. Le client la recharge par carte et paie ses commandes avec ; chaque
# vente crédite l'épargne du marchand, qui la vire ensuite vers son compte bancaire.

MAX_TOPUP = 500  # € par recharge
MOVEMENTS_SHOWN = 50


def record_movement(conn: psycopg.Connection, customer_id: int, kind: str, amount, label: str):
    conn.execute(
        "INSERT INTO wallet_movements (customer_id, kind, amount, label) VALUES (%s, %s, %s, %s)",
        (customer_id, kind, amount, label),
    )


def read_wallet(conn: psycopg.Connection, customer_id: int) -> dict:
    balance, merchant = conn.execute(
        "SELECT balance, is_merchant FROM customers WHERE id = %s", (customer_id,)
    ).fetchone()
    rows = conn.execute(
        "SELECT kind, amount, label, created_at FROM wallet_movements WHERE customer_id = %s "
        "ORDER BY id DESC LIMIT %s",
        (customer_id, MOVEMENTS_SHOWN),
    ).fetchall()
    return {
        "balance": float(balance),
        "merchant": merchant,  # le site s'aligne dessus si le rôle a changé depuis la connexion
        "movements": [
            {"kind": kind, "amount": float(amount), "label": label, "created_at": created_at.isoformat()}
            for kind, amount, label, created_at in rows
        ],
    }


@app.get("/shop/wallet")
def get_wallet(customer_id: int = Depends(require_customer)):
    """Solde et derniers mouvements du compte connecté (cagnotte, ou épargne du marchand)."""
    with connect() as conn:
        return read_wallet(conn, customer_id)


@app.post("/shop/wallet/topup")
def top_up(body: TopUpIn, customer_id: int = Depends(require_customer)):
    """Recharge par carte. La carte n'est pas transmise (boutique fictive) ; la recharge
    crée une transaction, vue par le dashboard, et échoue pendant l'incident."""
    if state["broken"]:
        raise HTTPException(500, "erreur interne du service de paiement")
    amount = round(body.amount, 2)
    if not 1 <= amount <= MAX_TOPUP:
        raise HTTPException(422, f"recharge entre 1 et {MAX_TOPUP} €")
    with connect() as conn, conn.transaction():
        conn.execute(
            "INSERT INTO transactions (id, amount, currency, status) VALUES (%s, %s, 'EUR', 'accepted')",
            (str(uuid.uuid4()), amount),
        )
        conn.execute("UPDATE customers SET balance = balance + %s WHERE id = %s", (amount, customer_id))
        record_movement(conn, customer_id, "topup", amount, "Recharge par carte")
        return read_wallet(conn, customer_id)


@app.post("/shop/orders")
def create_order(body: OrderIn, customer_id: int = Depends(require_customer)):
    # Pendant l'incident, le paiement échoue comme /transactions : c'est ce que
    # le client constate, et ce que la reprise automatique doit rétablir.
    if state["broken"]:
        raise HTTPException(500, "erreur interne du service de paiement")
    product_ids = [item.product_id for item in body.items]
    if not body.items or any(item.quantity < 1 for item in body.items) or len(set(product_ids)) != len(product_ids):
        raise HTTPException(422, "panier vide, quantité invalide ou produit en double")
    order_id, tx_id = str(uuid.uuid4()), str(uuid.uuid4())
    # Une seule transaction SQL : si un produit manque ou si la cagnotte ne suffit pas,
    # rien n'est débité ni enregistré.
    with connect() as conn, conn.transaction():
        total, lines = 0, []
        for item in body.items:
            # Le prix vient de la base, jamais du navigateur. Le stock ne baisse que
            # s'il suffit, vérifié et décrémenté en une requête (pas de survente).
            row = conn.execute(
                "UPDATE products SET stock = stock - %s WHERE id = %s AND stock >= %s AND NOT archived RETURNING price",
                (item.quantity, item.product_id, item.quantity),
            ).fetchone()
            if row is None:
                raise HTTPException(409, f"produit {item.product_id} introuvable ou stock insuffisant")
            total += row[0] * item.quantity
            lines.append((order_id, item.product_id, item.quantity, row[0]))
        # Débit de la cagnotte, vérifié et appliqué en une requête (pas de solde négatif).
        debited = conn.execute(
            "UPDATE customers SET balance = balance - %s WHERE id = %s AND balance >= %s RETURNING balance",
            (total, customer_id, total),
        ).fetchone()
        if debited is None:
            raise HTTPException(402, f"cagnotte insuffisante : il faut {total} € (rechargez votre cagnotte)")
        label = f"Commande n° {order_id[:8]}"
        record_movement(conn, customer_id, "purchase", -total, label)
        # Le marchand est crédité dans la même transaction : l'argent ne se perd ni ne se crée.
        merchant = conn.execute(
            "SELECT id FROM customers WHERE email = %s AND is_merchant", (MERCHANT_EMAIL,)
        ).fetchone()
        if merchant:
            conn.execute("UPDATE customers SET balance = balance + %s WHERE id = %s", (total, merchant[0]))
            record_movement(conn, merchant[0], "sale", total, label)
        conn.execute(
            "INSERT INTO transactions (id, amount, currency, status) VALUES (%s, %s, 'EUR', 'accepted')",
            (tx_id, total),
        )
        conn.execute(
            "INSERT INTO orders (id, customer_id, transaction_id, total, status) VALUES (%s, %s, %s, %s, 'paid')",
            (order_id, customer_id, tx_id, total),
        )
        for line in lines:
            conn.execute(
                "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s)",
                line,
            )
    return {"id": order_id, "transaction_id": tx_id, "total": float(total), "status": "paid",
            "balance": float(debited[0])}


@app.get("/shop/orders")
def list_orders(customer_id: int = Depends(require_customer)):
    """Historique d'achat du client connecté, et de lui seul."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT o.id, o.total, o.status, o.created_at, p.name, p.emoji, i.quantity, i.unit_price "
            "FROM orders o JOIN order_items i ON i.order_id = o.id JOIN products p ON p.id = i.product_id "
            "WHERE o.customer_id = %s ORDER BY o.created_at DESC, p.name",
            (customer_id,),
        ).fetchall()
    orders = {}  # regroupe les lignes par commande, dans l'ordre (plus récente d'abord)
    for order_id, total, status, created_at, name, emoji, quantity, unit_price in rows:
        order = orders.setdefault(order_id, {
            "id": order_id, "total": float(total), "status": status,
            "created_at": created_at.isoformat(), "items": [],
        })
        order["items"].append({"name": name, "emoji": emoji, "quantity": quantity, "unit_price": float(unit_price)})
    return list(orders.values())


# --- Espace marchand ------------------------------------------------------------

MAX_RESTOCK = 10_000  # borne par opération : une faute de frappe ne crée pas un stock absurde


def require_merchant(customer_id: int = Depends(require_customer)) -> int:
    """Le rôle est relu en base à chaque appel : le retirer prend effet tout de suite,
    sans attendre l'expiration du jeton."""
    with connect() as conn:
        row = conn.execute("SELECT is_merchant FROM customers WHERE id = %s", (customer_id,)).fetchone()
    if row is None or not row[0]:
        raise HTTPException(403, "réservé au marchand")
    return customer_id


@app.post("/shop/merchant/products/{product_id}/restock")
def restock_product(product_id: int, body: RestockIn, _=Depends(require_merchant)):
    """Ajoute des unités au stock d'une confiserie existante."""
    if not 1 <= body.quantity <= MAX_RESTOCK:
        raise HTTPException(422, f"quantité entre 1 et {MAX_RESTOCK}")
    with connect() as conn:
        row = conn.execute(
            f"UPDATE products SET stock = stock + %s WHERE id = %s AND NOT archived RETURNING {PRODUCT_COLUMNS}",
            (body.quantity, product_id),
        ).fetchone()
    if row is None:
        raise HTTPException(404, "produit introuvable")
    return product_dict(row)


@app.post("/shop/merchant/products")
def create_product(body: ProductIn, _=Depends(require_merchant)):
    """Ajoute une nouvelle confiserie au catalogue (sans photo, l'emoji la remplace)."""
    name, description, emoji = body.name.strip(), body.description.strip(), body.emoji.strip()
    if not name or not description or not emoji:
        raise HTTPException(422, "nom, description et emoji obligatoires")
    if len(name) > 80 or len(description) > 300 or len(emoji) > 8:
        raise HTTPException(422, "nom (80), description (300) ou emoji (8) trop long")
    if not 0 < body.price <= 1000:
        raise HTTPException(422, "prix entre 0,01 et 1000 €")
    if not 0 <= body.stock <= MAX_RESTOCK:
        raise HTTPException(422, f"stock entre 0 et {MAX_RESTOCK}")
    image = decode_image(body.image)
    with connect() as conn:
        row = conn.execute(
            "INSERT INTO products (name, description, price, stock, emoji, image) VALUES (%s, %s, %s, %s, %s, %s) "
            f"RETURNING {PRODUCT_COLUMNS}",
            (name, description, round(body.price, 2), body.stock, emoji, image),
        ).fetchone()
    return product_dict(row)


@app.delete("/shop/merchant/products/{product_id}")
def delete_product(product_id: int, _=Depends(require_merchant)):
    """Retire une confiserie du catalogue. Elle est archivée, pas effacée : les
    commandes passées la référencent et gardent ainsi leur historique."""
    with connect() as conn:
        row = conn.execute(
            f"UPDATE products SET archived = true WHERE id = %s AND NOT archived RETURNING {PRODUCT_COLUMNS}",
            (product_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(404, "produit introuvable")
    return product_dict(row)


def normalize_iban(iban: str) -> str:
    """IBAN sans espaces, en majuscules, validé par sa clé (ISO 13616, modulo 97)."""
    iban = "".join(iban.split()).upper()
    if not (15 <= len(iban) <= 34 and iban[:2].isalpha() and iban[2:4].isdigit() and iban.isalnum() and iban.isascii()):
        raise HTTPException(422, "IBAN invalide")
    digits = "".join(str(int(c, 36)) for c in iban[4:] + iban[:4])
    if int(digits) % 97 != 1:
        raise HTTPException(422, "IBAN invalide (clé de contrôle)")
    return iban


@app.post("/shop/merchant/payout")
def payout(body: PayoutIn, merchant_id: int = Depends(require_merchant)):
    """Virement de l'épargne du marchand vers son compte bancaire (fictif : rien ne part).
    Seuls le titulaire et les 4 derniers caractères de l'IBAN sont gardés dans le journal."""
    iban, holder, amount = normalize_iban(body.iban), body.holder.strip(), round(body.amount, 2)
    if not holder or len(holder) > 80:
        raise HTTPException(422, "titulaire du compte requis (80 caractères maximum)")
    if amount < 0.01:
        raise HTTPException(422, "montant invalide")
    with connect() as conn, conn.transaction():
        if conn.execute(
            "UPDATE customers SET balance = balance - %s WHERE id = %s AND balance >= %s RETURNING balance",
            (amount, merchant_id, amount),
        ).fetchone() is None:
            raise HTTPException(409, "épargne insuffisante pour ce virement")
        record_movement(conn, merchant_id, "payout", -amount, f"Virement vers {holder} ({iban[:4]} •••• {iban[-4:]})")
        return read_wallet(conn, merchant_id)
