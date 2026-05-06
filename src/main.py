from fastapi import FastAPI
from src.schemas import UserCreate

app = FastAPI(title="Corporate file manager — registration")

@app.post("/registration")
def registration(user: UserCreate) -> dict[str, str]:
    return {"msg": "User created", "user": user.username}
