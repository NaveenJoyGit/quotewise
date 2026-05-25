# QuoteWise Demo Guide

End-to-end walkthrough — no WhatsApp Business account required.

---

## Prerequisites

Install once on your machine before anything else.

| Tool | Version | Install |
|---|---|---|
| Docker Desktop | latest | https://www.docker.com/products/docker-desktop |
| Python `uv` | ≥ 0.4 | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js | ≥ 18 | https://nodejs.org |
| Google Cloud CLI (`gcloud`) | latest | https://cloud.google.com/sdk/docs/install |

> **Skip WeasyPrint** — PDF generation is optional for the demo.  
> If WeasyPrint is not installed the "Approve" step shows a note instead of a PDF link, which is fine.

---

## One-time setup

Do these steps once per machine. You do **not** need to repeat them between demo runs.

### 1. Clone and enter the repo

```bash
git clone <repo-url>
cd quotewise
```

### 2. Authenticate with Google Cloud (Vertex AI)

```bash
gcloud auth application-default login
```

Follow the browser prompt. This writes credentials to `~/.config/gcloud/`.  
The backend reads them automatically when `LLM_PROVIDER=vertex`.

### 3. Create the environment file

Most settings have working defaults. The only values you must supply are your GCP project ID and the LLM provider switch.

```bash
cat > backend/.env <<'EOF'
LLM_PROVIDER=vertex
GCP_PROJECT_ID=<your-gcp-project-id>
EOF
```

Replace `<your-gcp-project-id>` with the real project ID:

```bash
gcloud config get-value project
```

Everything else (`DATABASE_URL`, `REDIS_URL`, `PDF_STORAGE_DIR`, model names) has a sensible default in `backend/app/core/config.py` and does not need to be set for a local demo.

### 4. Install Python dependencies

```bash
cd backend
uv sync
cd ..
```

### 5. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### 6. Create a `.env.local` for the frontend

```bash
echo 'NEXT_PUBLIC_API_URL=http://localhost:8000' > frontend/.env.local
```

---

## Starting the stack

Open **four terminal tabs** (or panes) and run one command per tab, in order.

### Tab 1 — PostgreSQL + Redis (Docker)

```bash
docker compose up -d postgres redis
```

Wait ~5 seconds until both containers show `healthy`:

```bash
docker compose ps
```

### Tab 2 — Database migrations + seed data

Run this once (or after `docker compose down -v` to reset):

```bash
cd backend
uv run alembic upgrade head
uv run python ../scripts/seed_data.py
```

You should see `Seeded contractor: Demo Painter Co.` (or similar).

### Tab 3 — FastAPI backend

```bash
cd backend
uv run uvicorn app.main:app --reload --port 8000
```

Verify it is up:

```bash
curl -s http://localhost:8000/healthz
# → {"status":"ok"}
```

### Tab 4 — Next.js frontend

```bash
cd frontend
npm run dev
```

The dev server starts at **http://localhost:3000**.

---

## Demo script

### Open the demo UI

Navigate to **http://localhost:3000/demo** in Chrome or Firefox.

You will see a two-pane layout:
- **Left** — buyer's WhatsApp chat (green bubbles)
- **Right** — contractor view (initially shows "Waiting for quote…")

---

### Conversation flow (painting example)

Type each message in the left pane and press **Enter** or click **Send**.

| Your message | What the AI does |
|---|---|
| `Hi, I need a quote` | Greets the buyer, asks about the work |
| `Interior painting` | Identifies scope (painting), asks for area |
| `2000 sqft` | Records area, asks about quality/finish |
| `Premium emulsion, 2 coats` | Records finish, checks for missing slots |
| `Living room and bedrooms` | All slots filled → calculates price |

After the last message the right pane switches from "Waiting" to showing a **quote card** with line items and totals.

---

### Approving the quote

Click **Approve & Generate PDF** on the right pane.

- The backend generates a PDF via WeasyPrint and saves it to `backend/pdfs/`.
- The button changes to **Open PDF** (click to view).
- If WeasyPrint is not installed you will see "PDF generation skipped" — the quote is still marked `approved` in the database.

### Rejecting the quote

Click **Reject** instead. The quote is marked `rejected` in the database.

---

### Checking the dashboard

All generated quotes are visible at **http://localhost:3000/quotes**.

On first visit you will be redirected to the login page.  
Your API key was printed by the seed script, or you can look it up:

```bash
cd backend
uv run python -c "
from app.db.base import SessionLocal
from app.db.models import Contractor
db = SessionLocal()
c = db.query(Contractor).first()
print(c.api_key)
db.close()
"
```

Paste the UUID into the login field and click **Sign in**.

---

### Starting a new conversation

Click **Reset conversation** at the top-right of the demo page.  
A fresh `session_id` is generated in the browser, so the AI starts from scratch.

---

## Onboarding a new contractor (optional)

Visit **http://localhost:3000/onboarding** to walk through the three-step setup:

1. **Business Profile** — name, phone, city
2. **Rate Card** — upload a PDF/CSV; AI parses it into a rate table you can edit
3. **Go Live** — copy the buyer WhatsApp link and save your API key

After onboarding the new contractor's pricing is active and will be picked up automatically by the demo chat (if they are the first contractor in the DB) or via the WhatsApp webhook once a WA Business Account is connected.

---

## Troubleshooting

### "Could not reach the backend"

- Is `uvicorn` running in Tab 3?  
- Is the port 8000 free? (`lsof -i :8000`)

### AI replies are wrong or generic

- `LLM_PROVIDER` in `backend/.env` must be `vertex`, not `mock`.
- Run `gcloud auth application-default login` again if credentials expired.
- Check `GCP_PROJECT_ID` is the project where **Vertex AI API** is enabled (Gemini 2.5 Flash/Pro).

### "No contractor found. Run scripts/seed_data.py first"

Run `uv run python ../scripts/seed_data.py` from the `backend/` directory.

### Postgres connection refused

The Docker container may not be ready yet. Run `docker compose up -d postgres` and wait 10 seconds.

### PDF not generated

WeasyPrint requires system libraries (`pango`, `cairo`).  
On macOS: `brew install pango cairo`  
On Ubuntu: `apt-get install -y libpango-1.0-0 libcairo2`  
Then reinstall: `uv sync`

---

## Stopping the stack

```bash
# Stop the dev servers with Ctrl-C in Tabs 3 and 4, then:
docker compose down
```

To also wipe the database (start fresh):

```bash
docker compose down -v
```
