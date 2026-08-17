from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.clientip import get_client_ip
from app.config import METRIKA_ID, RATE_LIMIT_PER_DAY
from app.counter import count_text, metric_labels
from app.fetcher import fetch_visible_text, FetchError
from app.limiter import check_limit, close_db, init_db, ping_db, record_request


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


class AnalyzeRequest(BaseModel):
    url: str


# HEAD — для аптайм-мониторинга: многие проверяльщики ходят именно им.
@app.api_route("/", response_class=HTMLResponse, methods=["GET", "HEAD"])
async def index(request: Request):
    return templates.TemplateResponse(
        request, "index.html", {"metrics": metric_labels(), "metrika_id": METRIKA_ID}
    )


# Для мониторинга: без шаблона и без сети, но с проверкой базы — если она
# недоступна, /analyze тоже работать не будет.
@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    try:
        await ping_db()
    except Exception:
        return JSONResponse({"status": "error"}, status_code=503)
    return {"status": "ok"}


@app.post("/analyze")
async def analyze(data: AnalyzeRequest, request: Request):
    ip = get_client_ip(request)

    if not await check_limit(ip):
        return JSONResponse(
            {"error": f"Превышен лимит запросов ({RATE_LIMIT_PER_DAY} в день)"},
            status_code=429,
        )

    # Списываем попытку до загрузки: иначе запросы с ошибкой лимит не тратят,
    # и сервисом можно бесплатно сканировать чужие сайты.
    await record_request(ip)

    try:
        text = await fetch_visible_text(data.url)
    except FetchError as e:
        return JSONResponse({"error": str(e)}, status_code=422)

    return count_text(text)
