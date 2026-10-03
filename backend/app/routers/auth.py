from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_invite_code,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.db.models import Household, RefreshToken, User
from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserRead,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_read(user: User, household: Household) -> UserRead:
    return UserRead(
        id=user.id,
        email=user.email,
        nome=user.nome,
        household_id=user.household_id,
        household_invite_code=household.invite_code,
    )


async def _issue_tokens(db: AsyncSession, user: User, household: Household) -> TokenResponse:
    access_token = create_access_token(str(user.id), str(user.household_id))
    refresh_token = generate_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(refresh_token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    await db.commit()
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=_user_read(user, household),
    )


@router.post("/register", response_model=TokenResponse)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(User).where(User.email == body.email))
    if existing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email già registrata")

    if body.invite_code:
        household = await db.scalar(select(Household).where(Household.invite_code == body.invite_code))
        if household is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Codice invito non valido")
    else:
        household = Household(invite_code=generate_invite_code())
        db.add(household)
        await db.flush()

    user = User(
        household_id=household.id,
        email=body.email,
        password_hash=hash_password(body.password),
        nome=body.nome,
    )
    db.add(user)
    await db.flush()

    return await _issue_tokens(db, user, household)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == body.email))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenziali non valide")
    household = await db.get(Household, user.household_id)
    return await _issue_tokens(db, user, household)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    token_hash = hash_refresh_token(body.refresh_token)
    existing = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    now = datetime.now(timezone.utc)
    if existing is None or existing.revoked_at is not None or existing.expires_at < now:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token non valido o scaduto")

    existing.revoked_at = now
    user = await db.get(User, existing.user_id)
    household = await db.get(Household, user.household_id)
    return await _issue_tokens(db, user, household)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: LogoutRequest, db: AsyncSession = Depends(get_db)):
    token_hash = hash_refresh_token(body.refresh_token)
    existing = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if existing and existing.revoked_at is None:
        existing.revoked_at = datetime.now(timezone.utc)
        await db.commit()


@router.get("/me", response_model=UserRead)
async def me(current: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user = await db.get(User, current.user_id)
    household = await db.get(Household, user.household_id)
    return _user_read(user, household)
