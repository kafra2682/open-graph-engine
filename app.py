import os
import sys
import urllib.parse
from typing import Optional
from fastapi import FastAPI, Query, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
import trafilatura

app = FastAPI(
    title="Article Extraction API - Ultra Tolerant",
    version="1.3.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def esegui_estrazione(raw_url: str):
    if not raw_url:
        raise HTTPException(status_code=400, detail="Parametro 'url' mancante.")
    
    decoded_url = urllib.parse.unquote(raw_url.strip())
    if not decoded_url.startswith(("http://", "https://")):
        decoded_url = "https://" + decoded_url

    try:
        # Download della pagina usando il modulo di download nativo di trafilatura
        downloaded = trafilatura.fetch_url(decoded_url)
        if not downloaded:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Impossibile scaricare la pagina all'URL previsto: {decoded_url}"
            )

        # Estrazione del testo principale (restituisce una stringa di testo puro)
        text_content = trafilatura.extract(
            downloaded, 
            include_comments=False, 
            include_tables=True
        )
        
        if not text_content:
            raise HTTPException(
                status_code=status.HTTP_204_NO_CONTENT,
                detail="Nessun contenuto leggibile estratto dalla pagina richiesta."
            )

        # Estrazione sicura dei metadati (titolo, autore, data)
        metadata = trafilatura.extract_metadata(downloaded)
        
        return {
            "status": "success",
            "url": decoded_url,
            "title": getattr(metadata, "title", None) if metadata else None,
            "author": getattr(metadata, "author", None) if metadata else None,
            "date": getattr(metadata, "date", None) if metadata else None,
            "text": text_content,
            "length": len(text_content)
        }

    except HTTPException as http_ex:
        # Rilancia le eccezioni HTTP controllate (es. 422 o 204) senza trasformarle in 500
        raise http_ex
    except Exception as e:
        # Blocco anti-crash: intercetta qualsiasi altro errore imprevisto trasformandolo in un 400 gestito
        raise HTTPException(
            status_code=400,
            detail=f"Errore interno durante il parsing dell'articolo: {str(e)}"
        )

# --- ROTTE UNIVERSALI (Catturano qualsiasi chiamata per evitare il 404) ---

@app.get("/extract")
@app.get("/extract/")
def extract_universal_get(url: Optional[str] = Query(None)):
    if not url:
        raise HTTPException(status_code=400, detail="Parametro 'url' richiesto nella query string.")
    return esegui_estrazione(url)

@app.post("/extract")
@app.post("/extract/")
async def extract_universal_post(request: Request):
    try:
        payload = await request.json()
        url = payload.get("url")
    except Exception:
        url = None
    if not url:
        raise HTTPException(status_code=400, detail="Parametro 'url' richiesto nel body JSON.")
    return esegui_estrazione(url)

@app.get("/")
def home_or_fallback(request: Request, url: Optional[str] = Query(None)):
    if url:
        return esegui_estrazione(url)
    return {
        "status": "online", 
        "service": "Article Extraction API",
        "note": "Usa l'endpoint /extract?url=... per estrarre i dati."
    }
