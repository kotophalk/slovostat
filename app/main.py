from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.counter import count_text
from app.fetcher import fetch_visible_text, FetchError
from app.limiter import check_limit, record_request

app = FastAPI()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


class AnalyzeRequest(BaseModel):
    url: str


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.post("/analyze")
async def analyze(data: AnalyzeRequest, request: Request):
    ip = request.client.host

    if not await check_limit(ip):
        return JSONResponse(
            {"error": "Превышен лимит запросов (25 в день)"},
            status_code=429,
        )

    try:
        text = await fetch_visible_text(data.url)
    except FetchError as e:
        return JSONResponse({"error": str(e)}, status_code=422)

    await record_request(ip)
    return count_text(text)
