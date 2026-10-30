from fastapi import APIRouter, Depends
from app.api.deps import Services, get_services
from app.api.errors import ApiError
from app.data.indicators import catalog_listing
from app.demo_models.registry import load_manifest

router = APIRouter(tags=["meta"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/health/db")
def health_db(services: Services = Depends(get_services)):
    try:
        services.repository.ping()
    except Exception:
        raise ApiError(503, "database_unavailable", "The database could not be reached.")
    return {"status": "ok", "database": "reachable"}


@router.get("/indicators")
def indicators():
    return {"indicators": catalog_listing()}


@router.get("/demo-models")
def demo_models():
    return {"models": load_manifest()}
