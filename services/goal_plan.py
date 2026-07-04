"""Goal plan calculator.

Pure functions (no I/O) so they're easy to unit-test. Given a user's profile and a
target weight + pace, computes the daily calorie goal, macros, time-to-goal, and any
safety limits that were triggered. Supports reverse calculation from a desired duration.

Numbers here are common fitness-calculator heuristics, NOT medical norms.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

# Activity multipliers (Mifflin-St Jeor TDEE).
ACTIVITY = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "high": 1.725,
    "veryhigh": 1.9,
}

# Nominal pace per mode (kg/week) before safeguards clamp it.
PACE_MODES = {
    "light": 0.25,
    "moderate": 0.5,
    "good": 0.75,
    "aggressive": 1.0,
}

KCAL_PER_KG = 7700.0          # ~energy in 1 kg of body fat
CALORIE_FLOOR = {"male": 1500, "female": 1200}
RATE_CAP_FRACTION = 0.01      # max 1% of body weight per week
DEFICIT_CAP_FRACTION = 0.35   # deficit ≤ 35% of TDEE


def _bmr(weight: float, height: float, age: float, gender: str) -> float:
    base = 10 * weight + 6.25 * height - 5 * age
    return base + (5 if gender == "male" else -161)


def _macros(kcal: float, weight: float) -> dict:
    """Protein tied to bodyweight, fat 27% of calories, carbs the remainder —
    same split the onboarding uses so the calorie ring stays consistent."""
    p = round(weight * 1.8)
    f = round(kcal * 0.27 / 9)
    c = max(0, round((kcal - p * 4 - f * 9) / 4))
    return {"p": p, "f": f, "c": c}


def compute_plan(
    *,
    weight: float,
    height: float,
    age: float,
    gender: str,
    activity: str,
    target_weight: float,
    pace_mode: str | None = None,
    pace: float | None = None,
    desired_weeks: int | None = None,
    today: date | None = None,
) -> dict:
    """Return the goal plan.

    Provide the pace in one of three ways (priority in this order):
      - `desired_weeks`: reverse calc — derive the pace needed to hit the goal in N weeks.
      - `pace`: explicit kg/week.
      - `pace_mode`: one of PACE_MODES ("light"/"moderate"/"good"/"aggressive").
    """
    today = today or date.today()
    gender = "male" if gender == "male" else "female"
    activity_mult = ACTIVITY.get(activity, 1.55)
    floor = CALORIE_FLOOR[gender]

    bmr = _bmr(weight, height, age, gender)
    tdee = bmr * activity_mult

    weight_diff = abs(weight - target_weight)
    if weight_diff < 0.05:
        direction = "maintain"
    else:
        direction = "lose" if target_weight < weight else "gain"

    warnings: list[dict] = []

    # ---- resolve the requested pace (kg/week) ----
    reverse = False
    if desired_weeks and desired_weeks > 0:
        reverse = True
        requested_rate = weight_diff / desired_weeks
    elif pace is not None:
        requested_rate = abs(pace)
    else:
        requested_rate = PACE_MODES.get(pace_mode or "moderate", 0.5)

    # Maintenance (or target == current): nothing to clamp.
    if direction == "maintain":
        daily = round(tdee)
        return {
            "direction": "maintain",
            "daily_kcal": daily,
            "macros": _macros(daily, weight),
            "weeks": 0,
            "target_date": today.isoformat(),
            "requested_pace_kg_per_week": round(requested_rate, 2),
            "effective_pace_kg_per_week": 0.0,
            "bmr": round(bmr),
            "tdee": round(tdee),
            "warnings": warnings,
        }

    requested_delta = requested_rate * KCAL_PER_KG / 7  # kcal/day deficit or surplus

    # ---- safeguards → effective daily delta ----
    rate_cap = RATE_CAP_FRACTION * weight                    # kg/week ceiling
    cap_by_rate = rate_cap * KCAL_PER_KG / 7                 # kcal/day
    caps = [cap_by_rate]
    if requested_rate > rate_cap + 1e-9:
        warnings.append({
            "code": "rate_capped",
            "message": f"Темп ограничен до {rate_cap:.2f} кг/нед — это потолок 1% массы тела "
                       f"в неделю, быстрее небезопасно.",
        })

    if direction == "lose":
        cap_by_pct = DEFICIT_CAP_FRACTION * tdee
        cap_by_floor = tdee - floor
        caps += [cap_by_pct, cap_by_floor]
        effective_delta = max(0.0, min([requested_delta] + caps))

        # Which loss-specific safeguard is binding?
        eps = 1.0
        if effective_delta < requested_delta - eps:
            if abs(effective_delta - cap_by_floor) <= eps and cap_by_floor <= cap_by_pct:
                warnings.append({
                    "code": "floor_capped",
                    "message": f"Дневная норма не может быть ниже {floor} ккал. Темп снижен, "
                               f"чтобы не опускаться ниже безопасного минимума.",
                })
            elif abs(effective_delta - cap_by_pct) <= eps:
                warnings.append({
                    "code": "deficit_capped",
                    "message": "Дефицит ограничен 35% от суточного расхода — так безопаснее.",
                })
        effective_target = tdee - effective_delta
    else:  # gain — only the 1%-body-weight rate cap applies
        effective_delta = max(0.0, min(requested_delta, cap_by_rate))
        effective_target = tdee + effective_delta

    daily = round(effective_target)
    effective_rate = effective_delta * 7 / KCAL_PER_KG

    if effective_rate > 1e-6:
        weeks = math.ceil(weight_diff / effective_rate)
        target_date = (today + timedelta(weeks=weeks)).isoformat()
    else:
        weeks = None
        target_date = None
        warnings.append({
            "code": "unreachable",
            "message": "При текущем профиле безопасно двигаться к этой цели не получается — "
                       "измени целевой вес или темп.",
        })

    # Reverse calc infeasibility: asked for a duration the safeguards won't allow.
    if reverse and effective_rate < requested_rate - 1e-3:
        warnings.append({
            "code": "duration_infeasible",
            "message": "Выбранный срок недостижим безопасно. Используется максимально "
                       f"допустимый темп (~{effective_rate:.2f} кг/нед)"
                       + (f", срок ~{weeks} нед." if weeks else "."),
        })

    return {
        "direction": direction,
        "daily_kcal": daily,
        "macros": _macros(daily, weight),
        "weeks": weeks,
        "target_date": target_date,
        "requested_pace_kg_per_week": round(requested_rate, 2),
        "effective_pace_kg_per_week": round(effective_rate, 2),
        "bmr": round(bmr),
        "tdee": round(tdee),
        "warnings": warnings,
    }
