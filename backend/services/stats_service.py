class StatsService:
    BASE_XP = 10
    COMPLETION_XP = 10

    @staticmethod
    def _number(stats: dict, key: str) -> int:
        try:
            value = int(stats.get(key, 0) or 0)
        except (TypeError, ValueError):
            value = 0
        return max(0, value)

    def process_quiz_answer(self, is_correct: bool, current_stats: dict | None) -> tuple[dict, str, int]:
        current_stats = current_stats or {}
        new_stats = {
            "quiz_total": self._number(current_stats, "quiz_total") + 1,
            "quiz_correct": self._number(current_stats, "quiz_correct"),
            "current_streak": self._number(current_stats, "current_streak"),
            "best_streak": self._number(current_stats, "best_streak"),
            "points": self._number(current_stats, "points"),
        }
        if is_correct:
            new_stats["quiz_correct"] += 1
            new_stats["current_streak"] += 1
            new_stats["best_streak"] = max(new_stats["best_streak"], new_stats["current_streak"])
            new_stats["points"] += self.BASE_XP
            return new_stats, f"Верно! +{self.BASE_XP} XP", self.BASE_XP
        new_stats["current_streak"] = 0
        return new_stats, "Неверно. Правильный ответ показан.", 0

    def award_quiz_completion(self, current_stats: dict | None) -> tuple[dict, int]:
        new_stats = dict(current_stats or {})
        new_stats["points"] = self._number(new_stats, "points") + self.COMPLETION_XP
        return new_stats, self.COMPLETION_XP

    def get_level_info(self, points: int) -> tuple[int, str]:
        points = max(0, self._number({"points": points}, "points"))
        level = (points // 10) + 1
        if level >= 50:
            title = "Кино-эксперт"
        elif level >= 20:
            title = "Главный критик"
        elif level >= 10:
            title = "Гик"
        elif level >= 5:
            title = "Киноман"
        else:
            title = "Стажёр"
        return level, title


stats_service = StatsService()
