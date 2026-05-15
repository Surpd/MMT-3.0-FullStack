class StatsService:
    def __init__(self):
        # Настройки баланса (можем менять в любой момент)
        self.BASE_WIN = 10
        self.BASE_LOSE = 5

    def process_quiz_answer(self, is_correct: bool, current_stats: dict) -> tuple[dict, str]:
        """
        Принимает ответ (True/False) и текущую статистику из БД.
        Возвращает обновленный словарь с цифрами и текст для ответа юзеру.
        """
        # Копируем текущие данные, чтобы обновить их
        new_stats = {
            "quiz_total": current_stats.get("quiz_total", 0) + 1,
            "quiz_correct": current_stats.get("quiz_correct", 0),
            "current_streak": current_stats.get("current_streak", 0),
            "best_streak": current_stats.get("best_streak", 0),
            "points": current_stats.get("points", 0)
        }

        if is_correct:
            # Верный ответ: растим счетчики
            new_stats["quiz_correct"] += 1
            new_stats["current_streak"] += 1
            
            # Считаем множитель за стрик
            multiplier = 1.0
            if new_stats["current_streak"] >= 5:
                multiplier = 2.0
            elif new_stats["current_streak"] >= 3:
                multiplier = 1.5
                
            points_gain = int(self.BASE_WIN * multiplier)
            new_stats["points"] += points_gain
            
            # Обновляем рекорд, если текущий стрик стал больше
            if new_stats["current_streak"] > new_stats["best_streak"]:
                new_stats["best_streak"] = new_stats["current_streak"]
                
            msg = f"✅ Верно! +{points_gain} XP"
            if multiplier > 1.0:
                msg += f" (Множитель x{multiplier} 🔥)"
        else:
            # Ошибка: сбрасываем стрик, отнимаем очки
            new_stats["current_streak"] = 0
            # Следим, чтобы баланс не ушел в минус
            new_stats["points"] = max(0, new_stats["points"] - self.BASE_LOSE) 
            msg = f"❌ Неверно! Вы потеряли {self.BASE_LOSE} XP. Стрик сброшен."

        return new_stats, msg

    def get_level_info(self, points: int) -> tuple[int, str]:
        """
        Математика уровней: 100 очков = 1 уровень.
        Возвращает кортеж (уровень, звание).
        """
        level = (points // 10) + 1
        
        # Раздаем звания в зависимости от уровня
        if level >= 50:
            title = "🏆 Кино-бог"
        elif level >= 20:
            title = "🧠 Главный критик"
        elif level >= 10:
            title = "🎥 Гик"
        elif level >= 5:
            title = "🍿 Киноман"
        else:
            title = "🎬 Стажёр"
            
        return level, title

# Создаем готовый объект, чтобы импортировать его в хендлеры
stats_service = StatsService()