from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.db.models import Household
from app.db.session import get_db
from app.schemas.household import HouseholdSettingsRead, HouseholdSettingsUpdate

router = APIRouter(prefix="/households", tags=["households"])


async def _get_household(db: AsyncSession, household_id) -> Household:
    household = await db.get(Household, household_id)
    if household is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Household non trovato")
    return household


@router.get("/me/settings", response_model=HouseholdSettingsRead)
async def get_settings(
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_household(db, current.household_id)


@router.patch("/me/settings", response_model=HouseholdSettingsRead)
async def update_settings(
    body: HouseholdSettingsUpdate,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    household = await _get_household(db, current.household_id)
    household.correggi_orientamento = body.correggi_orientamento
    await db.commit()
    await db.refresh(household)
    return household
