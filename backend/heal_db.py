import asyncio
from config import db, tmdb

async def heal_posters():
    print("🔍 Ищем фильмы без постеров в базе...")
    
    # Ищем фильмы, где poster_url пустой (null)
    query = db._client.table("movies").select("id, media_type, title").is_("poster_url", "null")
    response = await db._execute(query)
    
    movies_to_heal = response.data if response and response.data else []
    
    if not movies_to_heal:
        print("✅ Все фильмы с постерами, лечить нечего!")
        return

    print(f"🚑 Найдено фильмов без обложек: {len(movies_to_heal)}")

    fixed_count = 0
    for m in movies_to_heal:
        m_id = m["id"]
        m_type = m.get("media_type", "movie")
        
        print(f"🔄 Пробуем вылечить: {m.get('title', m_id)}...")
        
        try:
            # Идем в TMDB за свежими данными
            details = await tmdb.get_movie_details(m_id, media_type=m_type)
            
            if details and details.poster_url:
                # Обновляем запись в базе
                update_query = db._client.table("movies").update({"poster_url": details.poster_url}).eq("id", m_id)
                await db._execute(update_query)
                fixed_count += 1
                print(f"   🟢 Успешно! Добавлен постер: {details.poster_url}")
            else:
                print(f"   🔴 В TMDB тоже нет постера для этого фильма.")
                
        except Exception as e:
            print(f"   ❌ Ошибка при обновлении {m_id}: {e}")
            
        # Небольшая пауза, чтобы не спамить TMDB
        await asyncio.sleep(0.5)

    print(f"\n🎉 Готово! Вылечено обложек: {fixed_count} из {len(movies_to_heal)}")

if __name__ == "__main__":
    # Запускаем скрипт
    asyncio.run(heal_posters())