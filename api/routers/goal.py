"""Goal feature API.

POST /api/goal/preview — compute a plan without saving (live preview in the Mini App).
PUT  /api/goal        — save the goal, persist the computed calorie target + macros, return the plan.

The user's body profile (weight/height/age/gender/activity) is read from the DB; the
request only carries the target weight and the chosen pace (or a desired duration).
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.auth import get_telegram_user
from db.database import AsyncSessionFactory
from db.models import User
from services.goal_plan import compute_plan

router = APIRouter()

# Defaults mirror the Mini App onboarding defaults, so a missing field never 500s.
_DEFAULTS = {"gender": "female", "age": 28, "weight": 70.0, "height": 170.0, "activity": "moderate"}


class GoalInput(BaseModel):
    target_weight: float
    pace_mode: str | None = None       # light / moderate / good / aggressive
    desired_weeks: int | None = None


def profile_kwargs(user: User | None, weight_override: float | None = None) -> dict:
    """Build compute_plan() profile kwargs from a User row, filling gaps with defaults."""
    if user is None:
        base = dict(_DEFAULTS)
    else:
        base = {
            "gender": user.gender or _DEFAULTS["gender"],
            "age": user.age or _DEFAULTS["age"],
            "weight": user.weight_kg or _DEFAULTS["weight"],
            "height": user.height_cm or _DEFAULTS["height"],
            "activity": user.activity_level or _DEFAULTS["activity"],
        }
    if weight_override is not None:
        base["weight"] = weight_override
    return base


def _plan(user: User | None, payload: GoalInput) -> dict:
    return compute_plan(
        target_weight=payload.target_weight,
        pace_mode=payload.pace_mode,
        desired_weeks=payload.desired_weeks,
        **profile_kwargs(user),
    )


@router.post("/goal/preview")
async def preview_goal(payload: GoalInput, tg_user: dict = Depends(get_telegram_user)):
    user_id: int = tg_user["id"]
    async with AsyncSessionFactory() as session:
        user = await session.get(User, user_id)
    return _plan(user, payload)


@router.put("/goal")
async def save_goal(payload: GoalInput, tg_user: dict = Depends(get_telegram_user)):
    user_id: int = tg_user["id"]
    first_name: str = tg_user.get("first_name", "")

    async with AsyncSessionFactory() as session:
        user = await session.get(User, user_id)
        if user is None:
            user = User(telegram_id=user_id, first_name=first_name)
            session.add(user)

        plan = _plan(user, payload)

        # Persist the goal and make its calorie target the app-wide operative target.
        user.target_weight_kg = payload.target_weight
        user.pace_kg_per_week = plan["requested_pace_kg_per_week"]
        user.goal = plan["direction"]
        user.target_kcal = plan["daily_kcal"]
        user.target_protein_g = plan["macros"]["p"]
        user.target_fat_g = plan["macros"]["f"]
        user.target_carbs_g = plan["macros"]["c"]

        await session.commit()

    return plan
