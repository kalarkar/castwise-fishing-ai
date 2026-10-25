

@app.get("/api/conditions")
def conditions(location: str = "Lake Ontario — Whitby"):
    if location not in WEATHER_SITES:
        raise HTTPException(400, "Choose a supported fishing location")
    lat, lon, station, station_name = WEATHER_SITES[location]
    params = (f"latitude={lat}&longitude={lon}&timezone=America%2FToronto&forecast_days=3"
              "&current=temperature_2m,wind_speed_10m,wind_direction_10m,wind_gusts_10m,weather_code"
              "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max")
    try:
        data = json.loads(fetch_cached('weather:'+location, 'https://api.open-meteo.com/v1/forecast?'+params, 900))
        weather = {"current": data.get("current", {}), "daily": data.get("daily", {}),
                   "source": "Open-Meteo forecast", "updated": data.get("current",{}).get("time")}
    except Exception:
        import logging
        logging.exception("Open-Meteo weather API failed for location=%s", location)
        weather = {"current": {}, "daily": {}, "source": "Open-Meteo forecast", "error": "Weather temporarily unavailable"}
    water = {"celsius": None, "observed_at": None, "station": station_name,
             "status": "No recent verified water temperature available", "source": "NOAA NDBC buoy" if station else None}
    if station:
        try:
            raw = fetch_cached('buoy:'+station, f'https://www.ndbc.noaa.gov/data/realtime2/{station}.txt', 900).decode('ascii',errors='replace')
            lines = [x.split() for x in raw.splitlines() if x.strip()]
            hdr = lines[0]
            # Header first timestamp field may be '#YY'.
            i = hdr.index('WTMP')
            now = datetime.now(timezone.utc)
            for cols in lines[2:]:
                if len(cols)<=i or cols[i] in ('MM','99.0','999.0'): continue
                try:
                    yy=int(cols[0]); year=2000+yy if yy<100 else yy
                    when=datetime(year,int(cols[1]),int(cols[2]),int(cols[3]),int(cols[4]),tzinfo=timezone.utc)
                    temp=float(cols[i])
                    if timedelta(0)<=now-when<=timedelta(hours=12) and -2<=temp<=40:
                        water.update(celsius=temp, observed_at=when.isoformat(), status="Observed near-surface buoy temperature")
                        break
                except (ValueError,IndexError):continue
        except Exception: pass
    return {"location": location, "weather": weather, "water": water,
            "note": "Weather is a forecast. Buoy water temperature, if present, is a station observation, not a lake-wide measurement."}


@app.post("/api/chat", response_model=ChatResponse)
def chat(body: ChatRequest, request: Request, response: Response):
    if not os.getenv("GROQ_API_KEY") or os.getenv("GROQ_API_KEY") == "replace_with_your_groq_api_key":
        raise HTTPException(503, "Add GROQ_API_KEY to your .env file and restart the server.")
    uid = client_id(request, response)
    ip = request.client.host if request.client else "unknown"
    today = daily_key()
    # Atomic reservation: failed upstream requests are refunded below.
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        used = conn.execute("SELECT used FROM ai_usage WHERE user_id=? AND day=?", (uid,today)).fetchone()
        ip_used = conn.execute("SELECT used FROM ip_usage WHERE ip=? AND day=?", (ip,today)).fetchone()
        if used and used['used'] >= MAX_DAILY: raise HTTPException(429, "You have used your 3 free AI questions today. Resets at midnight Toronto time.")
        # Loose IP safety cap to discourage cookie resets; NAT users may share an IP.
        if ip_used and ip_used['used'] >= 30: raise HTTPException(429, "Daily shared-network AI usage limit reached. Please try tomorrow.")
        conn.execute("INSERT INTO ai_usage(user_id,day,used) VALUES (?,?,1) ON CONFLICT(user_id,day) DO UPDATE SET used=used+1", (uid,today))
        conn.execute("INSERT INTO ip_usage(ip,day,used) VALUES (?,?,1) ON CONFLICT(ip,day) DO UPDATE SET used=used+1", (ip,today))
    try:
        from langchain.agents import create_agent
        from langchain_groq import ChatGroq

        model_id = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        model = ChatGroq(model=model_id, temperature=0.3)
        agent = create_agent(model=model, tools=[], system_prompt=SYSTEM_PROMPT)
        messages = []
        # Accept only known roles and bounded history; never let clients inject system messages.
        for item in body.history[-8:]:
            role = item.get("role")
            content = item.get("content", "")
            if role in ("user", "assistant") and isinstance(content, str) and content.strip():
                messages.append({"role": role, "content": content[:2000]})
        context = []
        if body.location.strip():
            context.append(f"Fishing location: {body.location.strip()}")
        if body.species.strip():
            context.append(f"Target species: {body.species.strip()}")
        prompt = "\n".join(context + [f"Question: {body.message}"])
        messages.append({"role": "user", "content": prompt})
        result = agent.invoke({"messages": messages})
        answer = result["messages"][-1].content
        if isinstance(answer, list):
            answer = "\n".join(str(part.get("text", "")) if isinstance(part, dict) else str(part) for part in answer)
        return ChatResponse(answer=str(answer), model=model_id, remaining=max(0,MAX_DAILY-(used["used"] if used else 0)-1))
    except Exception as exc:
        with db() as conn:
            conn.execute("UPDATE ai_usage SET used=MAX(0,used-1) WHERE user_id=? AND day=?", (uid,today))
            conn.execute("UPDATE ip_usage SET used=MAX(0,used-1) WHERE ip=? AND day=?", (ip,today))
        # No secrets or internal stack traces sent to the client.
        detail = str(exc).lower()
        if "model_not_found" in detail or "does not exist" in detail or "404" in detail:
            raise HTTPException(502, "Groq model unavailable. Check GROQ_MODEL and your account's available models.") from exc
        if "rate_limit" in detail or "429" in detail:
            raise HTTPException(429, "Groq rate limit reached. Try again after your limit resets.") from exc
        if "api_key" in detail or "401" in detail:
            raise HTTPException(502, "Groq authentication failed. Verify your API key in .env.") from exc
        raise HTTPException(502, "Could not reach the AI service. Check the server terminal for details.") from exc


@app.get("/api/catches")
def get_catches():
    with db() as conn:
        rows = conn.execute("SELECT * FROM catches ORDER BY caught_on DESC, id DESC LIMIT 200").fetchall()
    return [dict(row) for row in rows]


@app.post("/api/catches", status_code=201)
def add_catch(catch: CatchIn):
    try:
        datetime.strptime(catch.caught_on, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(422, "Date must be a valid YYYY-MM-DD date") from exc
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO catches (species,location,caught_on,lure,length_cm,notes,created_at) VALUES (?,?,?,?,?,?,?)",
            (catch.species.strip(), catch.location.strip(), catch.caught_on, catch.lure.strip(), catch.length_cm, catch.notes.strip(), datetime.now(timezone.utc).isoformat()),
        )
        row = conn.execute("SELECT * FROM catches WHERE id=?", (cur.lastrowid,)).fetchone()
    return dict(row)


@app.delete("/api/catches/{catch_id}", status_code=204)
def delete_catch(catch_id: int):
    with db() as conn:
        result = conn.execute("DELETE FROM catches WHERE id=?", (catch_id,))
        if result.rowcount == 0:
            raise HTTPException(404, "Catch not found")
