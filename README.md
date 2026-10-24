# Castwise — Fishing AI Starter

A local, beginner-friendly fishing advisor and catch journal built with **FastAPI + LangChain + Groq + SQLite**. Designed for Windows and VS Code with **uv**.

## Run it on Windows

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and open this folder in VS Code.
2. In VS Code's PowerShell terminal run:
   ```powershell
   uv sync
   Copy-Item .env.example .env
   ```
3. Edit `.env` and set your own `GROQ_API_KEY` from <https://console.groq.com/keys>. Do not share this key.
4. Start the server:
   ```powershell
   uv run uvicorn app:app --reload --host 127.0.0.1 --port 8000
   ```
5. Open <http://127.0.0.1:8000> in your browser.

No Jupyter kernel is needed: this project is a normal Python web app, not an `.ipynb` notebook.

## Features

- Chat with Groq via a LangChain `create_agent` agent, configured for Ontario freshwater fishing.
- Choose your fishing location and target species.
- Save, view, and delete catches in a local SQLite file (`catches.db`).
- Responsive web UI, no Node.js build required.
- Built-in explanation for missing keys, rate limits and unavailable Groq models.

## Project files

- `app.py` — FastAPI routes, LangChain agent, database.
- `static/index.html` — browser frontend.
- `pyproject.toml` — uv dependencies.
- `.env.example` — example environment variables.
- `tests/test_app.py` — smoke tests.

## If you see Groq 404 "model not found"

The model accessible to your account might differ from the default. Sign into the [Groq console](https://console.groq.com/) to see currently supported models, then change `GROQ_MODEL` in `.env` and restart the server. The default is `openai/gpt-oss-120b`.

## Important limitations

- This **local development prototype** has no user accounts, cloud hosting, or authentication. **Do not expose it publicly** without authorization, rate limiting, security review, and a deployment setup.
- The model does **not** fetch live weather, Ontario fishing rules, or real-time fishing reports. Never rely on its guesses about those.
- Groq Free Plan is subject to provider limits and model availability. External APIs and eventual deployment can cost money.
- Catch data is stored locally. Back up `catches.db` to avoid losing records.


## Version 0.2: conditions and AI limits

- Three AI questions per day **per anonymous browser cookie**, reset at midnight America/Toronto. A basic shared-IP guard caps use at 30 requests per day per observed IP. This is a **beta abuse deterrent, not a secure paid-account quota**: cookies can be cleared, and shared networks may hit the IP cap. Add accounts and a persistent managed database before selling subscriptions.
- API endpoints: `/api/quota` and `/api/conditions?location=Lake%20Simcoe`.
- Open-Meteo serves the 3-day air temperature, rain probability and wind forecasts. Results are cached for 15 minutes. **Open-Meteo's free API is non-commercial only**: obtain their commercial licence or use a commercially permitted provider before accepting subscriptions or advertising.
- Lake Ontario water temperature comes from station **45139, West Lake Ontario – Grimsby** (NOAA NDBC / ECCC). An observation is displayed only if it is no more than 12 hours old, and is **not a Whitby measurement**. Other lakes currently display 'Unavailable' unless an authoritative source is connected. The app never substitutes air temperature for water temperature.
- Set `CASTWISE_SECRET_KEY` to a random, stable, secret value for a deployed instance. Without it the program creates `.castwise-secret` locally; ephemeral hosting may regenerate it and reset anonymous identity. Don't commit that secret or `.env`.
- The current catch journal is still shared between visitors and uses local SQLite. **Do not put this beta online with public catch journal enabled** until user logins, access controls and durable storage are implemented. SQLite on ephemeral hosting is not persistent.
