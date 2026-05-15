# utils/states.py
from aiogram.fsm.state import State, StatesGroup

class RecsState(StatesGroup):
    viewing_recs = State()  # Состояние "Пользователь листает пачку рекомендаций"