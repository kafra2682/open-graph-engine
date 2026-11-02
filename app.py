import os
import re
from typing import Optional
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
import httpx
from bs4 import BeautifulSoup
import trafilatura

app = FastAPI(
    title="Article & Web Content Extractor API",
    description="API ad alte prestazioni per l'estrazione pulita di testo e metadati da qualsiasi URL.",
    version="1.1.0"
)

# Configurazione CORS per consentire chiamate da RapidAPI e frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Headers realistici per aggirare protezioni anti-scraping (Cloudflare, Akamai, 403 Forbidden)
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,it;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.google.com/",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "cross-site",
    "Sec-Fetch-User": "?1",
}

class ExtractRequest(BaseModel):
    url: HttpUrl

class ExtractResponse(BaseModel):
    status: str
    url: str
    title: Optional[str] = None
    author: Optional[str] = None
    date: Optional[str] = None
    content: str
    word_count: int

async def fetch_and_extract(target_url: str) -> ExtractResponse:
    target_url_str = str(target_url)
    try:
        async with httpx.AsyncClient(
            headers=BROWSER_HEADERS,
            follow_redirects=True,
            timeout=15.0,
            verify=False
        ) as client:
            response = await client.get(target_url_str)
            
            if response.status_code == 403:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Accesso negato dal server di destinazione (403 Forbidden). Protezione anti-bot attiva."
                )
            if response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="La pagina di destinazione non esiste (404 Not Found)."
                )
            response.raise_for_status()
            html_content = response.text

    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Impossibile connettersi all'URL specificato: {str(exc)}"
        )

    # Estrazione primaria con Trafilatura
    extracted_text = trafilatura.extract(
        html_content,
        include_comments=False,
        include_tables=True,
        no_fallback=False
    )
    metadata = trafilatura.extract_metadata(html_content)

    title = metadata.title if metadata and metadata.title else None
    author = metadata.author if metadata and metadata.author else None
    date = metadata.date if metadata and metadata.date else None

    # Fallback su BeautifulSoup se Trafilatura non ottiene risultati sufficienti
    if not extracted_text or len(extracted_text.strip()) < 50:
        soup = BeautifulSoup(html_content, "html.parser")
        
        for element in soup(["script", "style", "nav", "footer", "header", "noscript", "aside", "svg"]):
            element.decompose()
            
        if not title and soup.title:
            title = soup.title.string.strip() if soup.title.string else None

        body = soup.find("body")
        if body:
            extracted_text = " ".join(body.stripped_strings)
        else:
            extracted_text = ""

    clean_text = re.sub(r"\s+", " ", extracted_text or "").strip()
    words = len(clean_text.split()) if clean_text else 0

    return ExtractResponse(
        status="success",
        url=target_url_str,
        title=title,
        author=author,
        date=date,
        content=clean_text,
        word_count=words
    )

# Endpoint configurato specificamente per RapidAPI (/extract sia POST che GET)
@app.post("/extract", response_model=ExtractResponse, tags=["Extraction"])
async def extract_article_post(payload: ExtractRequest):
    """Estrae il contenuto inviando un payload JSON: {'url': 'https://...' }"""
    return await fetch_and_extract(payload.url)

@app.get("/extract", response_model=ExtractResponse, tags=["Extraction"])
async def extract_article_get(url: HttpUrl = Query(..., description="URL della pagina da analizzare")):
    """Estrae il contenuto passando il parametro query: /extract?url=https://..."""
    return await fetch_and_extract(url)

# Aliases sulla Root (/) per evitare 404 in caso di configurazione base su RapidAPI
@app.post("/", response_model=ExtractResponse, include_in_schema=False)
async def extract_root_post(payload: ExtractRequest):
    return await fetch_and_extract(payload.url)

@app.get("/", tags=["Health Check"])
async def health_check():
    return {
        "status": "online",
        "service": "Article Extractor API",
        "active_endpoints": ["/extract", "/docs"]
    }
