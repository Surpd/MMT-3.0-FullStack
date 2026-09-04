# utils/states.py
from aiogram.fsm.state import State, StatesGroup

class RecsState(StatesGroup):
    viewing_recs = State()  # Состояние "Пользователь листает пачку рекомендаций"


class SearchState(StatesGroup):
    choosing_type = State()
    waiting_query = State()


class FilterState(StatesGroup):
    editing = State()
    waiting_min_year = State()
    waiting_max_year = State()
