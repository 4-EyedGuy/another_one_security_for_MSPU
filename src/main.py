from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.sanitize import sanitize_comment
from src.schemas import UserCreate

app = FastAPI(title="Corporate file manager — registration")

_BASE = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(_BASE / "templates"))

_comments_store: list[str] = []


@app.middleware("http")
async def csp_for_comments(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/comments"):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'"
        )
    return response


@app.get("/comments", response_class=HTMLResponse)
def comments_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "comments.html",
        {"comments": _comments_store},
    )


@app.post("/comments")
def comments_create(text: str = Form(...)) -> RedirectResponse:
    cleaned = sanitize_comment(text)
    _comments_store.append(cleaned)
    return RedirectResponse(url="/comments", status_code=303)


@app.post("/registration")
def registration(user: UserCreate) -> dict[str, str]:
    return {"msg": "User created", "user": user.username}
