# AutoAmend AI — backend

A small FastAPI service with three jobs:

1. **Hide the Mistral API key.** The Flutter app never talks to Mistral
   directly — it calls `POST /api/llm/complete` on this backend, which holds
   the key server-side and relays the request.
2. **Enforce the free-tier quota.** 3 free (billable) generations per
   device, then `402 quota_exceeded` until the device is subscribed.
3. **Verify Stripe subscriptions.** Creates Checkout Sessions and processes
   the webhook so subscription status is never trusted client-side.

It knows nothing about amendments, articles, or French legislative drafting
— all of that stays in the Flutter app (`amendment_llm_service.dart`). This
backend is a generic, dumb relay + gatekeeper.

## Endpoints

- `GET /api/status?device_id=...` → `{free_used, free_quota, subscribed}`
- `POST /api/llm/complete` → `{device_id, system, messages, temperature, max_tokens, json_mode, billable}` → `{content, free_used, free_quota, subscribed}` (or `402` when quota is exceeded and not subscribed)
- `POST /api/checkout` → `{device_id}` → `{url}` (Stripe Checkout URL)
- `POST /api/stripe/webhook` → Stripe webhook receiver
- `GET /success`, `GET /cancel` → plain HTML pages Stripe redirects to after checkout

## 1. Accounts you need

### Mistral (the LLM)
1. Sign up at https://console.mistral.ai
2. Create an API key under **API Keys** → copy it, this is `MISTRAL_API_KEY`.
3. Add a payment method under **Billing** (pay-as-you-go; `mistral-medium-latest`
   is priced per token, no subscription fee). Consider setting a monthly
   spend limit there too, as a safety net on top of the quota this backend
   already enforces.

### Supabase (the database)
1. Sign up at https://supabase.com (free tier).
2. **New project** → pick a name and a region close to where you'll host
   the backend (see Render step below) → set a **database password** and
   save it somewhere, you'll need it in a moment. Wait ~2 minutes for
   provisioning.
3. **Project Settings → Database → Connection string** → tab **URI**.
   Supabase shows something like:
   `postgresql://postgres.xxxxxxxx:[YOUR-PASSWORD]@aws-0-region.pooler.supabase.com:6543/postgres`
   Use the **pooler** connection (port `6543`) shown there, not the direct
   one — it handles the many short-lived connections a web backend opens
   much better.
4. Build `DATABASE_URL` from that string with two edits:
   - change the scheme from `postgresql://` to `postgresql+psycopg://`
     (our backend uses the `psycopg` driver)
   - replace `[YOUR-PASSWORD]` with the real database password from step 2

   Final shape:
   `postgresql+psycopg://postgres.xxxxxxxx:your-real-password@aws-0-region.pooler.supabase.com:6543/postgres`
5. Note: free Supabase projects pause after about a week of inactivity;
   the first request after a pause takes a few extra seconds while it
   wakes up. Not a problem for this app, just don't be surprised by it.

### Stripe (payments)
1. Sign up at https://dashboard.stripe.com (no card required to create the account).
2. Stay in **Test mode** first (toggle top-right) while we validate the flow.
3. Go to **Product catalog** → **Add product**:
   - Name: `AutoAmend AI Pro`
   - Pricing: **Recurring**, `7.99 EUR`, billing period **Monthly**.
   - Save, then open the price you just created and copy its ID
     (`price_...`) — this is `STRIPE_PRICE_ID`.
4. Go to **Developers → API keys** → copy the **Secret key** (`sk_test_...`
   for now) — this is `STRIPE_SECRET_KEY`.
5. The webhook secret (`STRIPE_WEBHOOK_SECRET`) is created in step 3 of the
   deployment below, once we know the backend's public URL.

## 2. Deploy to Render

The code is a flat set of modules (`main.py`, `config.py`, `db.py`,
`models.py`, `mistral_client.py`, `status.py`, `llm.py`, `billing.py`) sitting
side by side — no `app/` or `routes/` package, so there's nothing to import
with a dotted path.

1. Push this repo to GitHub (if not already).
2. On https://render.com, **New → Web Service**, connect the repo, set:
   - Runtime: `Python 3`
   - Root directory: leave **blank** if `main.py` sits at the repo's top
     level (a dedicated backend-only repo). If it's nested inside a bigger
     repo under a `backend/` folder instead, set this to `backend`.
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Instance type: Free
   - Environment variable `PYTHON_VERSION=3.12.7` (pins a well-supported version)
3. Under **Environment**, add the variables from `.env.example`
   (`MISTRAL_API_KEY`, `MISTRAL_MODEL`, `STRIPE_SECRET_KEY`,
   `STRIPE_PRICE_ID`, `DATABASE_URL`, `FREE_QUOTA`, `CORS_ORIGINS`,
   `PUBLIC_APP_URL`) — leave `STRIPE_WEBHOOK_SECRET` out for now.
   Set `PUBLIC_APP_URL` to the `https://your-service.onrender.com` URL Render
   assigns (shown once the first deploy finishes).
4. Deploy. Confirm `GET https://your-service.onrender.com/` returns
   `{"service": "AutoAmend AI backend", "status": "ok"}`.
5. Back in Stripe (still test mode): **Developers → Webhooks → Add endpoint**
   - URL: `https://your-service.onrender.com/api/stripe/webhook`
   - Events to send: `checkout.session.completed`,
     `customer.subscription.updated`, `customer.subscription.deleted`
   - Copy the **Signing secret** (`whsec_...`) it shows you.
6. Add `STRIPE_WEBHOOK_SECRET` to Render's environment variables with that
   value, and redeploy.
7. Once the Flutter web build's URL is known, add it to `CORS_ORIGINS`
   (comma-separated, e.g. `https://autoamend.netlify.app`) and redeploy.

## 3. Test locally before deploying

```bash
cd backend   # only if this folder is nested in a bigger repo; skip otherwise
python -m venv .venv && .venv/Scripts/activate   # Windows
pip install -r requirements.txt
cp .env.example .env   # fill in real values
uvicorn main:app --reload
```

Test the webhook locally with the [Stripe CLI](https://stripe.com/docs/stripe-cli):

```bash
stripe listen --forward-to localhost:8000/api/stripe/webhook
stripe trigger checkout.session.completed
```

## 4. Going live

When ready to accept real payments: flip Stripe to **Live mode**, recreate
the product/price and webhook endpoint there (test and live are separate),
and swap `STRIPE_SECRET_KEY` / `STRIPE_PRICE_ID` / `STRIPE_WEBHOOK_SECRET`
for their live-mode equivalents in Render's environment variables.
