import os
import asyncio
import httpx
from fastapi import FastAPI, HTTPException, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from bs4 import BeautifulSoup

app = FastAPI(
    title="Structured Data & OpenGraph Extraction Engine",
    description="API headless per l'estrazione di OpenGraph e dati strutturati per RapidAPI.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TIMEOUT_CONFIG = httpx.Timeout(10.0, connect=5.0)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

class ExtractionResponse(BaseModel):
    url: str
    title: str | None = None
    description: str | None = None
    image: str | None = None
    opengraph: dict
    json_ld: list

@app.get("/", tags=["Root"])
async def root():
    return {"status": "online", "engine": "Structured Data & OpenGraph Extraction Engine"}

@app.get("/extract", response_model=ExtractionResponse, tags=["Extraction"])
async def extract_data(
    url: HttpUrl = Query(..., description="L'URL completo del sito da scansionare"),
    # RapidAPI inoltra sempre questo header per identificare l'utente che chiama l'API
    x_rapidapi_user: str | None = Header(None, alias="X-Rapidapi-User", description="Identificativo utente gestito da RapidAPI")
):
    """
    Estrae tag OpenGraph e script JSON-LD. Riconosce l'utente tramite header di RapidAPI.
    """
    # Log temporaneo sul terminale per vedere chi sta chiamando l'API
    if x_rapidapi_user:
        print(f"[RapidAPI] Richiesta ricevuta dall'utente: {x_rapidapi_user}")
    else:
        print("[Local] Richiesta locale senza proxy RapidAPI")

    url_str = str(url)
    
    async with httpx.AsyncClient(timeout=TIMEOUT_CONFIG, follow_redirects=True) as client:
        try:
            headers = {"User-Agent": USER_AGENT}
            response = await client.get(url_str, headers=headers)
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=f"Errore host remoto: {response.status_code}")
        except httpx.RequestError as exc:
            raise HTTPException(status_code=504, detail=f"Timeout o errore di rete: {exc}")

    loop = asyncio.get_event_loop()
    try:
        data = await loop.run_in_executor(None, parse_html, response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore parsing: {str(e)}")

    return {"url": url_str, **data}

def parse_html(html_content: str) -> dict:
    soup = BeautifulSoup(html_content, "html.parser")
    opengraph = {}
    json_ld_data = []
    
    for meta in soup.find_all("meta"):
        property_attr = meta.get("property", "")
        name_attr = meta.get("name", "")
        if property_attr.startswith("og:") or name_attr.startswith("og:"):
            key = property_attr if property_attr else name_attr
            opengraph[key] = meta.get("content", "")

    import json
    for script in soup.find_all("script", type="application/ld+json"):
        if script.string:
            try:
                json_ld_data.append(json.loads(script.string.strip()))
            except json.JSONDecodeError:
                continue

    title = soup.title.string.strip() if soup.title and soup.title.string else None
    if not title:
        title = opengraph.get("og:title")
        
    description = opengraph.get("og:description")
    if not description:
        desc_meta = soup.find("meta", attrs={"name": "description"})
        description = desc_meta.get("content", "").strip() if desc_meta else None
        
    image = opengraph.get("og:image")

    return {
        "title": title,
        "description": description,
        "image": image,
        "opengraph": opengraph,
        "json_ld": json_ld_data
    }
