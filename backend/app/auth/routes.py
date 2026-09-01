from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from supabase import create_client
from app.config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

router = APIRouter(prefix="/auth", tags=["auth"])


class SignUpRequest(BaseModel):
    email: EmailStr
    password: str


class SignInRequest(BaseModel):
    email: EmailStr
    password: str


def _get_fresh_auth_client():
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


@router.post("/signup")
def signup(request: SignUpRequest):
    client = _get_fresh_auth_client()
    try:
        response = client.auth.sign_up({"email": request.email, "password": request.password})
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if response.user is None:
        raise HTTPException(status_code=400, detail="Sign up failed.")

    return {
        "user_id": response.user.id,
        "email": response.user.email,
        "session": {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
        } if response.session else None,
    }


@router.post("/signin")
def signin(request: SignInRequest):
    client = _get_fresh_auth_client()
    try:
        response = client.auth.sign_in_with_password(
            {"email": request.email, "password": request.password}
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if response.session is None:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    return {
        "user_id": response.user.id,
        "email": response.user.email,
        "session": {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
        },
    }