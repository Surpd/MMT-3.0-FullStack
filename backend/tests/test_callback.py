import asyncio
from datetime import datetime  # Тот самый импорт
from types import SimpleNamespace
from aiogram.types import User, Chat, Message, CallbackQuery, Update
from aiogram import Bot, Dispatcher

# Твои конфиги
from config import bot, dp, db, tmdb

# =========================
# ФЕЙК ОБЪЕКТЫ TELEGRAM
# =========================

def fake_user(user_id: int = 999999):
    return User(
        id=user_id,
        is_bot=False,
        first_name="Dmitrii",
        username="mitya"
    )

def fake_chat(chat_id: int = 999999):
    return Chat(id=chat_id, type="private")

def fake_message(text: str = "test"):
    # Если ты не видишь этот принт в консоли, значит файл не сохранился!
    # print(f"DEBUG: Создаем сообщение с датой {datetime.now()}") 
    
    return Message(
        message_id=1,
        date=datetime.now(),  # ТУТ ОБЯЗАТЕЛЬНО ДОЛЖНЫ БЫТЬ СКОБКИ ()
        chat=fake_chat(),
        from_user=fake_user(),
        text=text
    )

def fake_callback(data: str):
    return CallbackQuery(
        id="test_cb",
        from_user=fake_user(),
        chat_instance="test_instance",
        message=fake_message(),
        data=data
    )

# =========================
# СИМУЛЯТОРЫ
# =========================

async def simulate_callback(data: str):
    print(f"\n[SIMULATE CALLBACK] → {data}")
    cb = fake_callback(data)
    try:
        # Используем Update вместо SimpleNamespace для надежности в aiogram 3.x
        update = Update(update_id=1, callback_query=cb)
        await dp.feed_update(bot, update)
    except Exception as e:
        print(f"❌ [ERROR CB]: {e}")

async def simulate_message(text: str):
    print(f"\n[SIMULATE MESSAGE] → {text}")
    msg = fake_message(text)
    try:
        update = Update(update_id=1, message=msg)
        await dp.feed_update(bot, update)
    except Exception as e:
        print(f"❌ [ERROR MSG]: {e}")

# =========================
# ТЕСТОВЫЙ СЦЕНАРИЙ
# =========================

async def run_dev_tests():
    print("🚀 Запуск эмулятора 'Cinema Pilot'...")
    
    user_id = 999999
    movie_id = 157336  # Интерстеллар

    # Подготовка базы (чтобы Foreign Keys не ругались)
    print("\n[PREPARATION] Настройка окружения в БД...")
    await db.ensure_user(user_id)
    await db.save_movie({"id": movie_id, "title": "Интерстеллар", "media_type": "movie"})

    # Тесты кнопок
    await simulate_callback(f"status_liked_{movie_id}")
    await simulate_callback(f"rate_{movie_id}_5")

    # Тест квиза
    await simulate_message("🧠 Квиз")

    print("\n✅ СЦЕНАРИИ ОТРАБОТАНЫ")

if __name__ == "__main__":
    asyncio.run(run_dev_tests())