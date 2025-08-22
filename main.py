# main.py

import os
import io
import re
import math
from typing import List, Dict, Any, Tuple, Optional

import google.generativeai as genai

# Optional parsers for document handling
try:
    import PyPDF2
except Exception:
    PyPDF2 = None

try:
    import docx2txt
except Exception:
    docx2txt = None

try:
    import pandas as pd
except Exception:
    pd = None

import requests

# ----------------------------
# Environment / API setup
# ----------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyBzJVI8e7vVbT6lGZXSZiiz-ksH4zplCs0").strip()
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "0abded81f3eeb175a268f25ee1a32381").strip()

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        _MODEL = genai.GenerativeModel("gemini-1.5-flash")
    except Exception:
        _MODEL = None
else:
    _MODEL = None

def _gen(prompt: str) -> str:
    """Call Gemini safely and return response text or a graceful message."""
    if not _MODEL:
        return (
            "💡 (Gemini not configured) I can still help with offline checks. "
            "For richer answers, set GEMINI_API_KEY in your environment."
        )
    try:
        resp = _MODEL.generate_content(prompt)
        return (resp.text or "").strip()
    except Exception as e:
        return f"⚠️ Gemini error: {e}"

# ----------------------------
# Minimal port DB + geometry
# ----------------------------
PORTS: Dict[str, Tuple[float, float]] = {
    "singapore": (1.264, 103.822),
    "rotterdam": (51.955, 4.133),
    "mumbai": (18.95, 72.84),
    "dubai": (25.27, 55.29),
    "shanghai": (31.40, 121.50),
    "los angeles": (33.74, -118.26),
    "new york": (40.68, -74.04),
    "suez": (29.97, 32.55),
    "cape town": (-33.92, 18.44),
}

def haversine_nm(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance in nautical miles."""
    R_km = 6371.0
    R_nm = R_km * 0.539957
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlmb/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R_nm * c

def parse_distance_query(q: str) -> Tuple[str, str]:
    """
    Extract origin & destination from text like:
    - "distance between singapore and rotterdam"
    - "singapore to rotterdam"
    Returns (origin, destination) in lowercase if found, else ("","").
    """
    ql = q.lower()
    m = re.search(r"distance.*?(?:between|from)\s+([a-z\s]+?)\s+(?:and|to)\s+([a-z\s]+)", ql)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    m2 = re.search(r"([a-z\s]+?)\s+(?:to|->|→)\s+([a-z\s]+)", ql)
    if m2:
        return m2.group(1).strip(), m2.group(2).strip()
    return "", ""

# ----------------------------
# Documents: read & summarize
# ----------------------------
def read_text_from_file(file_name: str, file_bytes: bytes) -> str:
    ext = os.path.splitext(file_name)[1].lower()

    if ext == ".txt":
        try:
            return file_bytes.decode("utf-8", errors="ignore")
        except Exception:
            return file_bytes.decode("latin-1", errors="ignore")

    if ext == ".pdf" and PyPDF2:
        try:
            text = []
            with io.BytesIO(file_bytes) as f:
                pdf = PyPDF2.PdfReader(f)
                for page in pdf.pages:
                    text.append(page.extract_text() or "")
            return "\n".join(text).strip()
        except Exception as e:
            return f"PDF read error: {e}"

    if ext == ".docx" and docx2txt:
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                tmp.write(file_bytes)
                tmp.flush()
                content = docx2txt.process(tmp.name) or ""
            return content.strip()
        except Exception as e:
            return f"DOCX read error: {e}"

    if ext in (".csv", ".xlsx") and pd is not None:
        try:
            if ext == ".csv":
                df = pd.read_csv(io.BytesIO(file_bytes))
            else:
                df = pd.read_excel(io.BytesIO(file_bytes))
            return df.head(50).to_string(index=False)
        except Exception as e:
            return f"Table read error: {e}"

    return "Unsupported file type or missing parser. Try .txt, .pdf, .docx, .csv, or .xlsx."

SYSTEM_STYLE = """You are a Maritime AI Assistant. Be concise, structured, and practical.
If asked for laytime/demurrage, show step-by-step items and clear totals.
If asked for CP clauses, identify risks & highlight must-check clauses.
When summarizing docs, extract key terms, obligations, time bars, and demurrage rates if present.
Use bullet points & short sections.
"""

def summarize_document(doc_text: str) -> str:
    prompt = (
        f"{SYSTEM_STYLE}\n"
        f"Summarize the following maritime document. Extract:\n"
        f"- Document type & scope\n"
        f"- Parties, dates, ports\n"
        f"- Key obligations & time bars\n"
        f"- Laytime & demurrage terms (if any)\n"
        f"- Risks & recommended actions\n\n"
        f"--- DOCUMENT START ---\n{doc_text[:15000]}\n--- DOCUMENT END ---"
    )
    return _gen(prompt)

def suggest_docs_for_stage(stage: str) -> str:
    prompt = (
        f"{SYSTEM_STYLE}\n"
        f"Provide a checklist of actions & documents required for the '{stage}' stage.\n"
        f"Include: operational steps, risk checks, documents to prepare, and data to capture."
    )
    return _gen(prompt)

# ----------------------------
# Weather (live via OpenWeather)
# ----------------------------
def get_weather(city: str) -> str:
    if not OPENWEATHER_API_KEY:
        return "🌦 Live weather unavailable (no OPENWEATHER_API_KEY set)."
    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {"q": city, "appid": OPENWEATHER_API_KEY, "units": "metric"}
        r = requests.get(url, params=params, timeout=12)
        if r.status_code == 200:
            data = r.json()
            weather = data["weather"][0]["description"].title()
            temp = data["main"]["temp"]
            wind = data["wind"]["speed"]
            hum = data["main"].get("humidity", "?")
            return f"🌦 **{city.title()}** — {weather} • 🌡 {temp}°C • 💨 {wind} m/s • 💧 {hum}% RH"
        return f"⚠️ Could not fetch weather for **{city}** (HTTP {r.status_code})."
    except Exception as e:
        return f"⚠️ Weather API error: {e}"

# ----------------------------
# Hybrid chat router
# ----------------------------
def answer_query(user_message: str, chat_history: Optional[List[Dict[str, str]]] = None) -> str:
    """
    - Weather queries → live API
    - Distance queries → offline haversine + Gemini narrative
    - Everything else → Gemini (if available) else graceful offline note
    Returns: text_response
    """
    q = user_message.strip()
    ql = q.lower()

    # Weather intent (extract city words after 'in' or end)
    if "weather" in ql or "forecast" in ql:
        m = re.search(r"(?:in|at)\s+([a-zA-Z\s\-]+)$", q, re.IGNORECASE)
        if m:
            city = m.group(1).strip(" .!?,")
            return get_weather(city)
        tokens = [t for t in re.split(r"[^A-Za-z\-]+", q) if t]
        if tokens:
            return get_weather(tokens[-1])
        return get_weather("Singapore")

    # Distance intent
    a, b = parse_distance_query(q)
    if a and b and a in PORTS and b in PORTS:
        lat1, lon1 = PORTS[a]; lat2, lon2 = PORTS[b]
        nm = haversine_nm(lat1, lon1, lat2, lon2)
        prompt = (
            f"{SYSTEM_STYLE}\n"
            f"User asked distance between {a.title()} and {b.title()}.\n"
            f"Great-circle distance (approx): {nm:,.0f} nautical miles.\n\n"
            f"Now add: routing note (Suez/Cape if relevant), ETA at 12/14 knots, "
            f"and a brief fuel planning reminder."
        )
        return _gen(prompt)

    # Generic maritime Q&A via Gemini
    history_text = ""
    if chat_history:
        for m in chat_history[-8:]:
            role = m.get("role", "user")
            content = m.get("content", "")
            history_text += f"{role.upper()}: {content}\n"

    prompt = (
        f"{SYSTEM_STYLE}\n\n"
        f"Chat history (condensed):\n{history_text}\n"
        f"USER: {q}\n\n"
        f"Respond now with clear sections and bullet points if helpful."
    )
    return _gen(prompt)

# Convenience name kept from your earlier code
def hybrid_response(query: str, chat_history: Optional[List[Dict[str, str]]] = None) -> str:
    return answer_query(query, chat_history=chat_history)