from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, HttpUrl
import httpx
import random

app = FastAPI(
    title="Multi-Agent Data Ingestion API - Anti-Detection",
    version="1.1.0",
    description="Endpoint di ingestione con bypass 403 tramite fingerprinting HTTP/Headers avanzati."
)

# Pool di User-Agent realistici ed aggiornati
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
]

def build_stealth_headers() -> dict:
    """Genera header HTTP completi per simulare un browser reale e prevenire l'errore 403."""
    ua = random.choice(USER_AGENTS)
    is_firefox = "Firefox" in ua

    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,it-IT;q=0.8,it;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0"
    }

    if not is_firefox:
        headers["sec-ch-ua"] = '"Chromium";v="123", "Not:A-Brand";v="8"'
        headers["sec-ch-ua-mobile"] = "?0"
        headers["sec-ch-ua-platform"] = '"Windows"' if "Windows" in ua else '"macOS"'

    return headers

class ScrapeResponse(BaseModel):
    status_code: int
    url: str
    content_length: int
    content_preview: str

@app.get("/fetch", response_model=ScrapeResponse)
async def fetch_target(url: HttpUrl = Query(..., description="URL target da analizzare")):
    """Esegue una richiesta HTTP GET avanzata bypassando filtri anti-bot elementari e WAF base."""
    target_url = str(url)
    headers = build_stealth_headers()
    
    timeout_config = httpx.Timeout(15.0, connect=10.0)
    
    try:
        async with httpx.AsyncClient(headers=headers, timeout=timeout_config, follow_redirects=True) as client:
            response = await client.get(target_url)
            
            if response.status_code == 403:
                raise HTTPException(
                    status_code=403, 
                    detail="Errore 403: Blocco WAF/Cloudflare persistente. Necessario modulo Headless o Proxy residenziali."
                )
            
            response.raise_for_status()
            
            text_content = response.text
            return ScrapeResponse(
                status_code=response.status_code,
                url=target_url,
                content_length=len(text_content),
                content_preview=text_content[:500]
            )

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Errore HTTP target: {str(e)}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Errore di rete/connessione target: {str(e)}")

@app.get("/health")
def health_check():
    return {"status": "active", "phase": "1 - Anti-403 Hotfix Applied"}
