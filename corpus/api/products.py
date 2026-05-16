"""Product registration and heartbeat routes."""

import structlog
from fastapi import APIRouter, Depends, Query

from corpus.dependencies import get_product_service
from corpus.schemas import ProductHeartbeat, ProductRegistration
from corpus.services.product_service import ProductService

logger = structlog.get_logger()

router = APIRouter()


@router.post("/register", response_model=ProductRegistration, status_code=201)
async def register_product(
    payload: ProductRegistration,
    update_existing: bool = Query(default=False),
    service: ProductService = Depends(get_product_service),
) -> ProductRegistration:
    return await service.register(payload, update_existing=update_existing)


@router.post("/{product_id}/heartbeat", response_model=ProductRegistration)
async def heartbeat(
    product_id: str,
    payload: ProductHeartbeat,
    service: ProductService = Depends(get_product_service),
) -> ProductRegistration:
    return await service.heartbeat(product_id, payload)


@router.get("", response_model=list[ProductRegistration])
async def list_products(
    service: ProductService = Depends(get_product_service),
) -> list[ProductRegistration]:
    return await service.list_all()


@router.get("/{product_id}", response_model=ProductRegistration)
async def get_product(
    product_id: str,
    service: ProductService = Depends(get_product_service),
) -> ProductRegistration:
    return await service.get(product_id)


@router.delete("/{product_id}", status_code=204)
async def unregister_product(
    product_id: str,
    service: ProductService = Depends(get_product_service),
) -> None:
    await service.unregister(product_id)
