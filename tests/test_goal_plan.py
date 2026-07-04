"""Unit tests for services/goal_plan.compute_plan.

Run directly:  python tests/test_goal_plan.py
Or via pytest: pytest tests/test_goal_plan.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.goal_plan import compute_plan


def test_control_example():
    """TZ control case: man 90kg/180cm/30y, sedentary, 0.5 kg/wk, target 80kg."""
    plan = compute_plan(
        weight=90, height=180, age=30, gender="male",
        activity="sedentary", target_weight=80, pace_mode="moderate",
    )
    assert plan["direction"] == "lose"
    assert plan["daily_kcal"] == 1706, plan["daily_kcal"]
    assert plan["weeks"] == 20, plan["weeks"]
    assert plan["warnings"] == [], plan["warnings"]
    assert plan["effective_pace_kg_per_week"] == 0.5


def test_calorie_floor_safeguard():
    """Light woman, aggressive pace → daily target clamped to the 1200 floor."""
    plan = compute_plan(
        weight=55, height=165, age=30, gender="female",
        activity="sedentary", target_weight=50, pace_mode="aggressive",
    )
    assert plan["daily_kcal"] == 1200, plan["daily_kcal"]
    assert plan["effective_pace_kg_per_week"] < 1.0
    codes = {w["code"] for w in plan["warnings"]}
    assert "floor_capped" in codes, codes


def test_rate_cap_safeguard():
    """Aggressive 1.0 kg/wk on a 90kg person exceeds the 1% (0.9) ceiling."""
    plan = compute_plan(
        weight=90, height=180, age=30, gender="male",
        activity="high", target_weight=80, pace_mode="aggressive",
    )
    assert plan["effective_pace_kg_per_week"] <= 0.9 + 1e-9
    codes = {w["code"] for w in plan["warnings"]}
    assert "rate_capped" in codes, codes


def test_reverse_calc_feasible():
    """Desired 20 weeks for a 10kg loss → derived pace 0.5 kg/wk, matches control."""
    plan = compute_plan(
        weight=90, height=180, age=30, gender="male",
        activity="sedentary", target_weight=80, desired_weeks=20,
    )
    assert plan["daily_kcal"] == 1706, plan["daily_kcal"]
    assert plan["effective_pace_kg_per_week"] == 0.5
    assert not any(w["code"] == "duration_infeasible" for w in plan["warnings"])


def test_reverse_calc_infeasible():
    """Wanting a 10kg loss in 4 weeks is not safe → capped + infeasible warning."""
    plan = compute_plan(
        weight=90, height=180, age=30, gender="male",
        activity="sedentary", target_weight=80, desired_weeks=4,
    )
    codes = {w["code"] for w in plan["warnings"]}
    assert "duration_infeasible" in codes, codes
    assert plan["weeks"] is not None and plan["weeks"] > 4


def test_gain_direction():
    """Target above current → surplus, only the rate cap applies."""
    plan = compute_plan(
        weight=70, height=178, age=25, gender="male",
        activity="moderate", target_weight=75, pace_mode="light",
    )
    assert plan["direction"] == "gain"
    assert plan["daily_kcal"] > plan["tdee"]
    assert plan["weeks"] is not None


def test_maintain_when_target_equals_current():
    plan = compute_plan(
        weight=70, height=178, age=25, gender="male",
        activity="moderate", target_weight=70, pace_mode="moderate",
    )
    assert plan["direction"] == "maintain"
    assert plan["daily_kcal"] == plan["tdee"]
    assert plan["weeks"] == 0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
