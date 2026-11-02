import os
import sys
import urllib.parse
from typing import Optional
from fastapi import FastAPI, Query, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import trafilatura
from trafilatura.settings import use_config

app = FastAPI(
    title="Article Extraction API - Ultra Tolerant",
    version="1.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configurazione Trafilatura con User-Agent anti-blocco 403
trafilatura_config = use_config()
trafilatura_config.set("DEFAULT", "USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
trafilatura_config.set("DEFAULT", "DOWNLOAD_TIMEOUT", "15")

def esegui_estrazione(raw_url: str):
    if not raw_url:
        raise HTTPException(status_code=400, detail="Parametro 'url' mancante.")
    
    decoded_url = urllib.parse.unquote(raw_url.strip())
    if not decoded_url.startswith(("http://", "https://")):
        decoded_url = "https://" + decoded_url

    downloaded = trafilatura.fetch_url(decoded_url, config=trafilatura_config)
    if not downloaded:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Impossibile scaricare la pagina all'URL specificato: {decoded_url}"
        )

    result = trafilatura.extract(downloaded, include_comments=False, include_tables=True, output_format="python")
    if not result or not result.get("text"):
        raise HTTPException(
            status_code=status.HTTP_204_NO_CONTENT,
            detail="Nessun contenuto leggibile estratto dalla pagina richiesta."
        )

    text_content = result.get("text", "")
    return {
        "status": "success",
        "url": decoded_url,
        "title": result.get("title"),
        "author": result.get("author"),
        "date": result.get("date"),
        "text": text_content,
        "length": len(text_content)
    }

# --- ROTTE UNIVERSALI (Catturano qualsiasi combinazione per evitare il 404) ---

@app.get("/extract")
@app.get("/extract/")
def extract_universal_get(url: Optional[str] = Query(None)):
    if not url:
        raise HTTPException(status_code=400, detail="Parametro 'url' richiesto nella query string.")
    return esegui_estrazione(url)

@app.get("/")
def home_or_fallback(request: Request, url: Optional[str] = Query(None)):
    # Se RapidAPI invia per errore i parametri sulla root principale invece che su /extract
    if url:
        return esegui_estrazione(url)
    return {
        "status": "online", 
        "service": "Article Extraction API",
        "note": "Usa l'endpoint /extract?url=... per estrarre i dati."
    }
