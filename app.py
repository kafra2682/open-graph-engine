import urllib.parse
from typing import Optional
from fastapi import FastAPI, Query, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import trafilatura
from trafilatura.settings import use_config

app = FastAPI(
    title="Article Extraction API",
    description="High-performance extraction API compatible with RapidAPI GET/POST specifications",
    version="1.0.0"
)

# Configurazione CORS per accettare chiamate da RapidAPI console e frontend esterni
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configurazione Trafilatura con User-Agent realistico per evitare blocchi 403
trafilatura_config = use_config()
trafilatura_config.set("DEFAULT", "USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
trafilatura_config.set("DEFAULT", "DOWNLOAD_TIMEOUT", "15")

class ExtractRequest(BaseModel):
    url: str = Field(..., description="Target webpage URL to extract")

class ExtractResponse(BaseModel):
    status: str
    url: str
    title: Optional[str] = None
    author: Optional[str] = None
    date: Optional[str] = None
    text: Optional[str] = None
    length: int

def sanitize_and_extract(raw_url: str) -> dict:
    decoded_url = urllib.parse.unquote(raw_url.strip())
    
    if not decoded_url.startswith(("http://", "https://")):
        decoded_url = "https://" + decoded_url

    downloaded = trafilatura.fetch_url(decoded_url, config=trafilatura_config)
    
    if not downloaded:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Impossibile scaricare la pagina all'URL specificato: {decoded_url}"
        )

    result = trafilatura.extract(
        downloaded,
        include_comments=False,
        include_tables=True,
        output_format="python"
    )

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

@app.get("/")
def health_check():
    return {"status": "online", "service": "Article Extraction API"}

# Supporto nativo GET: accetta parametro URL come stringa grezza per evitare il parsing rigido di HttpUrl
@app.get("/extract", response_model=ExtractResponse)
@app.get("/extract/", response_model=ExtractResponse, include_in_schema=False)
def extract_get(
    url: str = Query(..., description="The full URL to extract (escaped or unescaped)")
):
    return sanitize_and_extract(url)

# Supporto nativo POST: garantisce compatibilità sia per payload JSON che form standard
@app.post("/extract", response_model=ExtractResponse)
@app.post("/extract/", response_model=ExtractResponse, include_in_schema=False)
def extract_post(payload: ExtractRequest):
    return sanitize_and_extract(payload.url)
