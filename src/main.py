from pathlib import Path
from copy import deepcopy

from fastapi import Depends, FastAPI, Form, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.sanitize import sanitize_comment
from src.schemas import UserCreate

app = FastAPI(title="Corporate file manager — registration")

_BASE = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(_BASE / "templates"))

_comments_store: list[str] = []
users_db = [
    {"id": 1, "username": "alice", "role": "user"},
    {"id": 2, "username": "bob", "role": "user"},
    {"id": 3, "username": "admin", "role": "admin"},
]
_files_seed = [
    {"id": 1, "name": "alice_report.pdf", "size": 1280, "owner_id": 1},
    {"id": 2, "name": "bob_notes.docx", "size": 2048, "owner_id": 2},
    {"id": 3, "name": "admin_policy.txt", "size": 512, "owner_id": 3},
]
files_db = deepcopy(_files_seed)


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


def get_current_user(x_user_id: int = Header(..., alias="X-User-Id")) -> dict:
    user = next((item for item in users_db if item["id"] == x_user_id), None)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user")
    return user


def check_file_permissions(
    file_id: int,
    current_user: dict = Depends(get_current_user),
) -> dict:
    file_item = next((item for item in files_db if item["id"] == file_id), None)
    if file_item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    if current_user["role"] == "admin" or file_item["owner_id"] == current_user["id"]:
        return file_item
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")


@app.get("/files/my")
def get_my_files(current_user: dict = Depends(get_current_user)) -> dict[str, list[dict]]:
    if current_user["role"] == "admin":
        return {"files": deepcopy(files_db)}
    own_files = [item for item in files_db if item["owner_id"] == current_user["id"]]
    return {"files": own_files}


@app.get("/files/all")
def get_all_files(current_user: dict = Depends(get_current_user)) -> dict[str, list[dict]]:
    if current_user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return {"files": deepcopy(files_db)}


@app.get("/files/{file_id}")
def get_file(file_item: dict = Depends(check_file_permissions)) -> dict[str, dict]:
    return {"file": file_item}


@app.delete("/files/{file_id}")
def delete_file(
    file_item: dict = Depends(check_file_permissions),
    current_user: dict = Depends(get_current_user),
) -> dict[str, str]:
    if current_user["role"] != "admin" and file_item["owner_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    files_db[:] = [item for item in files_db if item["id"] != file_item["id"]]
    return {"msg": "File deleted", "file": file_item["name"]}
