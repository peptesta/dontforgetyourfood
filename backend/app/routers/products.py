import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.db.models import Product
from app.db.session import get_db
from app.schemas.product import ProductRead, ProductUpdate
from app.services.image_storage import get_image_storage

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductRead])
async def list_products(
    stato: str = "attivo",
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Product).where(Product.household_id == current.household_id)
    if stato:
        query = query.where(Product.stato == stato)
    query = query.order_by(Product.data_scadenza.asc())
    result = await db.scalars(query)
    return result.all()


async def _get_owned_product(db: AsyncSession, current: CurrentUser, product_id: uuid.UUID) -> Product:
    product = await db.get(Product, product_id)
    if product is None or product.household_id != current.household_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prodotto non trovato")
    return product


@router.patch("/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: uuid.UUID,
    body: ProductUpdate,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    product = await _get_owned_product(db, current, product_id)
    if body.nome is not None:
        product.nome = body.nome
    if body.data_scadenza is not None:
        product.data_scadenza = body.data_scadenza
    await db.commit()
    await db.refresh(product)
    return product


@router.post("/{product_id}/consume", response_model=ProductRead)
async def consume_product(
    product_id: uuid.UUID,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    product = await _get_owned_product(db, current, product_id)
    product.stato = "consumato"
    await db.commit()
    await db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: uuid.UUID,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    product = await _get_owned_product(db, current, product_id)
    await db.delete(product)
    await db.commit()


@router.get("/{product_id}/foto-titolo")
async def get_product_title_photo(
    product_id: uuid.UUID,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    product = await _get_owned_product(db, current, product_id)
    if not product.foto_titolo_key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nessuna foto per questo prodotto")
    data = get_image_storage().load(product.foto_titolo_key)
    if data is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Foto non trovata")
    return Response(content=data, media_type="image/jpeg")
