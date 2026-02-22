# Internal Wallet Service

A **high-integrity internal wallet service** for gaming platforms, loyalty systems, or in-app credit economies. The system manages virtual credits (e.g. Gold Coins, Diamonds, Loyalty Points) in a closed loop: credits exist only inside the application, are not real money, and cannot be transferred between users. Every credit added or spent is recorded correctly; balances never go negative or out of sync; and no transactions are lost, even under heavy traffic or failures.

---

## Getting Started

### Prerequisites

- **Python 3.10+**
- **PostgreSQL 14+** (or any compatible version)

### 1. Spin up the database

Create a PostgreSQL database for the wallet service:

```bash
# Using psql (or your preferred client)
createdb wallet_db

# Or with Docker (one-off container)
docker run -d --name wallet-postgres -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=wallet_db -p 5432:5432 postgres:15-alpine
```

### 2. Configure the application

Clone the repo (or unzip the source), create a virtual environment, and install dependencies:

```bash
cd wallet-service
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
# source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root with your database URL:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/wallet_db
```

Adjust the URL to match your PostgreSQL host, port, user, password, and database name.

### 3. Create schema and run the seed script

The application creates the database tables on first startup. Then run the seed script to load initial data.

**Option A — Run app once, then seed:**

```bash
# Start the app once so it creates tables (Ctrl+C to stop after a few seconds)
uvicorn app.main:app --host 0.0.0.0 --port 8000

# In another terminal, run the seed script (requires psql and DATABASE_URL)
psql "$env:DATABASE_URL" -f seed.sql
# On macOS/Linux: psql $DATABASE_URL -f seed.sql
```

**Option B — Use Docker Compose (recommended):**

```bash
docker compose up -d
# App and DB start; seed runs automatically. See "Containerization" below.
```

### 4. Run the application

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- API: http://127.0.0.1:8000
- Interactive docs: http://127.0.0.1:8000/docs  

The seed script inserts:

- **Asset types:** Gold Coins (GOLD), Diamonds (DIAMONDS), Loyalty Points (LOYALTY_POINTS)
- **System accounts:** One treasury wallet per asset (source/sink for credits)
- **User accounts:** Two users (Alice, Bob) with initial balances in each asset

You can call the API immediately to top up, issue bonuses, spend, and check balances (see **API Endpoints** below).

---

## Technology Choice and Why


**Python** - Fast to implement, strong ecosystem for APIs and data validation. 
**FastAPI** - Async-capable, automatic OpenAPI docs, request validation with Pydantic. 
**PostgreSQL** - ACID transactions, row-level locking (`SELECT ... FOR UPDATE`), reliable and widely used. 
**SQLAlchemy** - Mature ORM with explicit transaction and locking control; fits ledger and concurrency needs. 
**Pydantic** - Request/response validation and clear API contracts. 

This stack gives explicit control over transactions and locking while keeping the codebase readable and easy to run.

---

## Strategy for Handling Concurrency

To avoid race conditions and balance corruption under high traffic:

1. **Row-level locking**  
   Every balance-changing operation locks the affected wallet rows with `SELECT ... FOR UPDATE` inside a single database transaction. Reads and updates for those wallets are serialized.

2. **Consistent lock order (deadlock avoidance)**  
   We always lock in the same order: **system (treasury) wallet first**, then **user wallet**. No transaction locks user A then user B while another locks user B then user A, so we avoid classic deadlock patterns.

3. **Balance check after lock**  
   For spend operations, we check “sufficient balance” only after acquiring the lock. That prevents two concurrent spends from both passing the check and overdrawing.

4. **Single transaction**  
   Each operation (top-up, bonus, spend) runs in one DB transaction: either all ledger entries and balance updates commit, or none do.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness check. |
| `GET` | `/db-check` | Simple DB connectivity check. |
| `GET` | `/transactions/balance?user_id=...&asset_code=...` | Get balance for a user’s wallet in the given asset. |
| `POST` | `/transactions/topup` | Top-up: user purchases credits (assume payment already done). |
| `POST` | `/transactions/bonus` | Bonus/incentive: issue free credits (e.g. referral). |
| `POST` | `/transactions/spend` | Spend: user pays credits for an in-app service. |

All mutation endpoints require an **idempotency key** in the body so retries do not double-apply.

**Example — Check balance:**

```bash
# Replace USER_ID with a user UUID from the seeded data (e.g. Alice or Bob)
curl "http://127.0.0.1:8000/transactions/balance?user_id=USER_ID&asset_code=GOLD"
```

**Example — Top-up (purchase):**

```json
POST /transactions/topup
{
  "user_id": "<user-uuid>",
  "asset_code": "GOLD",
  "amount": 50,
  "idempotency_key": "topup-unique-key-123"
}
```

**Example — Bonus:**

```json
POST /transactions/bonus
{
  "user_id": "<user-uuid>",
  "asset_code": "LOYALTY_POINTS",
  "amount": 100,
  "idempotency_key": "bonus-referal-456"
}
```

**Example — Spend:**

```json
POST /transactions/spend
{
  "user_id": "<user-uuid>",
  "asset_code": "GOLD",
  "amount": 30,
  "idempotency_key": "spend-purchase-789"
}
```

User and wallet UUIDs come from the seeded data; you can query the database or add a small script to list them if needed.

---

## Core Design Principles

### Ledger-Based Accounting

The service uses a **double-entry ledger** instead of only updating a balance column:

- Every logical transaction creates ledger entries.
- Each entry affects one wallet; amounts are signed (debit/credit).
- For each transaction, the sum of all ledger entries is **zero**.

Balances on `wallets` are cached for fast reads; the **ledger is the source of truth** for auditing and correctness.

### ACID Transactions

All balance-affecting operations run in a **single database transaction**, so either all changes commit or none do. Partial updates cannot occur on failure.

### Idempotency

Each mutation request carries an **idempotency key**, stored with a unique constraint. If the same key is sent again (e.g. retry), the API returns the **original** transaction result (same `transaction_id`, `credited` or `spent`) and does not apply the operation twice.

---

## Transaction Flows

1. **Wallet top-up (purchase)**  
   User buys credits (payment system assumed external). System debits treasury, credits user wallet; ledger entries and cached balances updated in one transaction.

2. **Bonus / incentive**  
   System grants free credits (e.g. referral). Same flow as top-up but recorded as type `BONUS` for auditing.

3. **Purchase / spend**  
   User spends credits for an in-app service. System checks balance under lock, debits user wallet, credits treasury; ledger and balances updated atomically. If balance is insufficient, the operation fails with no side effects.

---

## Containerization

The repo includes a **Dockerfile** and **docker-compose.yml** so you can run the app, database, and seed in one go.

**Run everything:**

```bash
docker compose up -d
```

This starts PostgreSQL and the wallet service. The app creates tables on startup; the `seed` service runs `seed.sql` automatically after the app is up. The API is available at http://127.0.0.1:8000

**Rebuild after code changes:**

```bash
docker compose up -d --build
```

---

## Project Structure

```
wallet-service/
├── app/
│   ├── main.py           # FastAPI app, table creation on startup
│   ├── db/
│   │   ├── base.py       # SQLAlchemy Base
│   │   ├── models.py     # User, Asset, Wallet, Transaction, LedgerEntry
│   │   ├── session.py    # Engine and session factory
│   │   └── deps.py       # get_db dependency
│   ├── routes/
│   │   └── transactions.py   # Top-up, bonus, spend, balance
│   ├── schemas/
│   │   └── transactions.py   # Pydantic request models
│   └── services/
│       └── wallet_service.py # Ledger logic, locking, idempotency
├── seed.sql
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```
