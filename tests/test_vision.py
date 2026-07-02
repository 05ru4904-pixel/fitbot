"""
Standalone script to test food recognition and calorie calculation prompts
without starting the bot.

Usage:
    cd d:\VS\FitBot
    python tests/test_vision.py path/to/food_photo.jpg
"""
import asyncio
import mimetypes
import os
import sys
from pathlib import Path

# Add project root to path and set working directory so .env is found
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from services.calorie_calc import calculate_calories
from services.vision import recognize_food


async def main():
    if len(sys.argv) < 2:
        print("Usage: python tests/test_vision.py <path_to_image>")
        sys.exit(1)

    image_path = Path(sys.argv[1])
    if not image_path.exists():
        print(f"File not found: {image_path}")
        sys.exit(1)

    mime, _ = mimetypes.guess_type(image_path.name)
    media_type = mime or "image/jpeg"

    print(f"Image: {image_path} ({media_type})")
    print("─" * 40)

    # Step 1: Recognition
    print("Step 1 — Recognizing food...")
    image_bytes = image_path.read_bytes()
    result = await recognize_food(image_bytes, media_type=media_type)

    print("\nRecognition result:")
    for dish in result.dishes:
        print(f"  • {dish.name}: ~{dish.estimated_weight_g} г  [{dish.confidence}]")
    print(f"  Overall confidence: {result.overall_confidence}")
    if result.notes:
        print(f"  Notes: {result.notes}")

    # Step 2: Calorie calculation
    print("\n" + "─" * 40)
    print("Step 2 — Calculating calories...")
    dishes = [d.model_dump() for d in result.dishes]
    calorie_result = await calculate_calories(dishes)

    print("\nCalorie result:")
    for item in calorie_result.items:
        print(
            f"  • {item.name} ({item.weight_g}г) — {int(item.calories)} ккал"
            f"  [Б:{item.protein_g:.1f} Ж:{item.fat_g:.1f} У:{item.carbs_g:.1f}]"
        )
    t = calorie_result.total
    print(f"\n  Итого: ~{calorie_result.calorie_range} ккал")
    print(f"  Б: {t.protein_g:.0f}г | Ж: {t.fat_g:.0f}г | У: {t.carbs_g:.0f}г")


if __name__ == "__main__":
    asyncio.run(main())
