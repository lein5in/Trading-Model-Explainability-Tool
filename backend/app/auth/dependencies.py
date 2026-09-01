from fastapi import Header, HTTPException
from app.db.client import get_supabase_client


def get_current_user_id(authorization: str = Header(None)) -> str:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header.")

    token = authorization.removeprefix("Bearer ").strip()

    client = get_supabase_client()
    try:
        response = client.auth.get_user(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired session token.")

    if response.user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session token.")

    return response.user.id