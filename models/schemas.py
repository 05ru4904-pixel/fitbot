from typing import Optional
from pydantic import BaseModel


class DishItem(BaseModel):
    name: str
    estimated_weight_g: int
    confidence: str  # "high" | "medium" | "low"


class RecognitionResult(BaseModel):
    dishes: list[DishItem]
    overall_confidence: str
    notes: Optional[str] = None


class NutritionItem(BaseModel):
    name: str
    weight_g: int
    calories: float
    protein_g: float
    fat_g: float
    carbs_g: float


class NutritionTotal(BaseModel):
    calories: float
    protein_g: float
    fat_g: float
    carbs_g: float


class CalorieResult(BaseModel):
    items: list[NutritionItem]
    total: NutritionTotal
    calorie_range: str
