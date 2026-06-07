from config import recommendation_service

TAG_NAMES = {
    28: "Боевики", 12: "Приключения", 16: "Мультфильмы", 35: "Комедии", 80: "Криминал",
    99: "Документалки", 18: "Драмы", 10751: "Семейные", 14: "Фэнтези", 36: "История",
    27: "Ужасы", 10402: "Музыкальные", 9648: "Детективы", 10749: "Мелодрамы",
    878: "Фантастика", 53: "Триллеры", 10752: "Военные", 37: "Вестерны"
}

DEFAULT_TAGS = ["Фантастика", "Комедии 2026", "Триллеры", "Боевики 2025", "Драмы"]

async def get_user_personalized_tags(user_id: int, limit: int = 4):
    smart_tags = ["Топ рейтинг", "Случайное кино"]
    
    if not user_id:
        return smart_tags + DEFAULT_TAGS

    try:
        # Достаем реальные жанры юзера из сервиса рекомендаций
        _, top_genres_ids, _, _, total_swipes = await recommendation_service._get_user_context(user_id)
        
        if total_swipes == 0 or not top_genres_ids:
            return smart_tags + ["Новинки 2026"] + DEFAULT_TAGS[:3]

        tags = []
        for g_id in top_genres_ids:
            try:
                # Принудительно переводим в int на случай, если БД вернула строку
                genre_name = TAG_NAMES.get(int(g_id))
                if genre_name:
                    tags.append(genre_name)
            except (ValueError, TypeError):
                continue
        
        # Добиваем дефолтными, если из профиля собралось слишком мало тегов
        for dt in DEFAULT_TAGS:
            if dt not in tags and len(tags) < limit:
                tags.append(dt)
                
        return smart_tags + tags
    except Exception as e:
        print(f"❌ [DEBUG TAGS ERROR]: {e}")
        return smart_tags + DEFAULT_TAGS