"""PUT /api/profile — update user profile from Mini App."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from api.auth import get_telegram_user
from db.database import AsyncSessionFactory
from db.models import User

router = APIRouter()


class Targets(BaseModel):
    kcal: float
    p: float
    f: float
    c: float


class ProfilePayload(BaseModel):
    gender: str | None = None
    goal: str | None = None
    age: int | None = None
    weight: float | None = None
    height: float | None = None
    activity: str | None = None
    targets: Targets | None = None


@router.put("/profile")
async def update_profile(
    payload: ProfilePayload,
    tg_user: dict = Depends(get_telegram_user),
):
    user_id: int = tg_user["id"]
    first_name: str = tg_user.get("first_name", "")

    async with AsyncSessionFactory() as session:
        user = await session.get(User, user_id)
        if not user:
            user = User(telegram_id=user_id, first_name=first_name)
            session.add(user)
        else:
            if first_name and not user.first_name:
                user.first_name = first_name

        if payload.gender is not None:
            user.gender = payload.gender
        if payload.goal is not None:
            user.goal = payload.goal
        if payload.age is not None:
            user.age = payload.age
        if payload.weight is not None:
            user.weight_kg = payload.weight
        if payload.height is not None:
            user.height_cm = payload.height
        if payload.activity is not None:
            user.activity_level = payload.activity
        if payload.targets is not None:
            user.target_kcal = payload.targets.kcal
            user.target_protein_g = payload.targets.p
            user.target_fat_g = payload.targets.f
            user.target_carbs_g = payload.targets.c

        await session.commit()

    return {"ok": True}
