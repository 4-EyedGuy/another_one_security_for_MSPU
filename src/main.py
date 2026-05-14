import os
from pathlib import Path
from copy import deepcopy
from uuid import uuid4
from io import BytesIO
import logging
import traceback

import filetype
from cryptography.fernet import Fernet
from dotenv import load_dotenv

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from src.sanitize import sanitize_comment
from src.schemas import UserCreate

load_dotenv()

_LOGS_DIR = Path("logs")
_LOGS_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(_LOGS_DIR / "app.log"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Corporate file manager — registration")

FERNET_KEY = os.getenv("FERNET_KEY")

if not FERNET_KEY:
    raise RuntimeError("FERNET_KEY not found in environment")

cipher = Fernet(FERNET_KEY.encode())

_BASE = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(_BASE / "templates"))
_STORAGE_DIR = _BASE / "storage"
_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
_MAX_FILE_SIZE = 2 * 1024 * 1024
_ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "text/plain"}

_comments_store: list[str] = []
users_db = [
    {"id": 1, "username": "alice", "role": "user"},
    {"id": 2, "username": "bob", "role": "user"},
    {"id": 3, "username": "admin", "role": "admin"},
]
_files_seed = [
    {
        "id": 1,
        "owner_id": 1,
        "original_name": "alice_report.pdf",
        "path": "",
        "size": 1280,
        "is_encrypted": False,
    },
    {
        "id": 2,
        "owner_id": 2, 
        "original_name": "bob_notes.docx",
        "path": "",
        "size": 2048,
        "is_encrypted": False,
    },
    {
        "id": 3,
        "owner_id": 3,
        "original_name": "admin_policy.txt",
        "path": "",
        "size": 512,
        "is_encrypted": False,
    },
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
        logger.warning(
            "Failed login attempt with X-User-Id=%s",
            x_user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user",
        )
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
    logger.warning(
        "Access denied: user=%s tried to access file_id=%s",
        current_user["username"],
        file_id,
    )
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="File not found",
    )


@app.get("/files/my")
def get_my_files(current_user: dict = Depends(get_current_user)) -> dict[str, list[dict]]:
    if current_user["role"] == "admin":
        return {"files": [_to_file_metadata(item) for item in files_db]}
    own_files = [item for item in files_db if item["owner_id"] == current_user["id"]]
    return {"files": [_to_file_metadata(item) for item in own_files]}


@app.get("/files/all")
def get_all_files(current_user: dict = Depends(get_current_user)) -> dict[str, list[dict]]:
    if current_user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return {"files": [_to_file_metadata(item) for item in files_db]}


@app.get("/files/{file_id}")
def get_file(file_item: dict = Depends(check_file_permissions)) -> dict[str, dict]:
    return {"file": _to_file_metadata(file_item)}


@app.delete("/files/{file_id}")
def delete_file(
    file_item: dict = Depends(check_file_permissions),
    current_user: dict = Depends(get_current_user),
) -> dict[str, str]:
    if current_user["role"] != "admin" and file_item["owner_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    stored_path = file_item.get("path", "")
    if stored_path:
        disk_path = _BASE / stored_path
        if disk_path.exists():
            disk_path.unlink()
    files_db[:] = [item for item in files_db if item["id"] != file_item["id"]]
    logger.info(
        "File deleted: user=%s file=%s",
        current_user["username"],
        file_item["original_name"],
    )
    return {"msg": "File deleted", "file": file_item["original_name"]}


def _to_file_metadata(file_item: dict) -> dict:
    owner = next((item for item in users_db if item["id"] == file_item["owner_id"]), None)
    return {
        "id": file_item["id"],
        "name": file_item["original_name"],
        "size": file_item["size"],
        "owner": owner["username"] if owner else "unknown",
        "is_encrypted": file_item["is_encrypted"],
    }


@app.post("/files/upload")
async def upload_file(
    encrypt: bool = False,
    uploaded_file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
) -> dict[str, object]:
    file_data = await uploaded_file.read()
    size = len(file_data)
    if size > _MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large",
        )
    kind = filetype.guess(file_data[:261])
    if uploaded_file.content_type == "text/plain":
        mime_type = "text/plain"
    elif kind is not None:
        mime_type = kind.mime
    else:
        mime_type = None
    if mime_type not in _ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type",
        )
    if mime_type == "image/jpeg":
        extension = ".jpg"
    elif mime_type == "image/png":
        extension = ".png"
    elif mime_type == "text/plain":
        extension = ".txt"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type",
        )
    filename = f"{uuid4().hex}{extension}"
    final_path = _STORAGE_DIR / filename
    data_to_save = file_data
    if encrypt:
        data_to_save = cipher.encrypt(file_data)
    with final_path.open("wb") as output:
        output.write(data_to_save)
    next_id = max((item["id"] for item in files_db), default=0) + 1
    record = {
        "id": next_id,
        "owner_id": current_user["id"],
        "original_name": uploaded_file.filename or filename,
        "path": f"storage/{filename}",
        "size": size,
        "is_encrypted": encrypt,
    }
    files_db.append(record)
    logger.info(
        "File uploaded: user=%s file=%s encrypted=%s",
        current_user["username"],
        uploaded_file.filename,
        encrypt,
    )
    return {
        "msg": "File uploaded",
        "encrypted": encrypt,
        "file": _to_file_metadata(record),
    }


@app.get("/files/{file_id}/download")
def download_file(file_item: dict = Depends(check_file_permissions)):
    stored_path = file_item.get("path", "")
    if not stored_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )
    disk_path = _BASE / stored_path
    if not disk_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )
    is_encrypted = file_item.get("is_encrypted", False)
    if not is_encrypted:
        return FileResponse(
            path=disk_path,
            filename=file_item["original_name"],
            media_type="application/octet-stream",
        )
    encrypted_data = disk_path.read_bytes()
    try:
        decrypted_data = cipher.decrypt(encrypted_data)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decrypt file",
        )
    return StreamingResponse(
        BytesIO(decrypted_data),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{file_item["original_name"]}"'
        },
    )

@app.get("/cause_error")
def cause_error():
    return 1 / 0