from __future__ import annotations
import re
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

class UserCreate(BaseModel):
    username: str = Field(
        ...,
        min_length=4,
        max_length=20,
        pattern=r"^[a-zA-Z0-9]+$",
    )
    email: EmailStr
    password: str
    confirm_password: str
    age: int = Field(..., ge=18, le=100)

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        if value == "123":
            raise ValueError("password is too weak")
        if not re.search(r"[A-Z]", value):
            raise ValueError("password must contain at least one uppercase letter")
        if not re.search(r"\d", value):
            raise ValueError("password must contain at least one digit")
        if not re.search(r"[!@#$%^&*]", value):
            raise ValueError(
                "password must contain at least one special character (!@#$%^&*)"
            )
        return value

    @model_validator(mode="after")
    def passwords_match(self) -> UserCreate:
        if self.password != self.confirm_password:
            raise ValueError("password and confirm_password do not match")
        return self
