from aiogram.fsm.state import State, StatesGroup


class FoodStates(StatesGroup):
    waiting_for_photo = State()
    confirming_composition = State()
    correcting = State()
    done = State()


class ProfileStates(StatesGroup):
    entering_gender = State()
    entering_age = State()
    entering_weight = State()
    entering_height = State()
    entering_activity = State()
