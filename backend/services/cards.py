from __future__ import annotations
from typing import Any
from services.tmdb import TMDB_IMAGE_BASE

class CardFormatter:
    _RU_MONTHS: dict[int, str] = {
        1: "Января", 2: "Февраля", 3: "Марта", 4: "Апреля", 5: "Мая", 6: "Июня",
        7: "Июля", 8: "Августа", 9: "Сентября", 10: "Октября", 11: "Ноября", 12: "Декабря",
    }

    @staticmethod
    def _build_image_url(path: str | None) -> str | None:
        return f"{TMDB_IMAGE_BASE}{path}" if path else None

    @staticmethod
    def _format_runtime(minutes: int | None) -> str:
        if not minutes or minutes <= 0: return "н/д"
        return f"{minutes // 60}ч {minutes % 60}м"

    @staticmethod
    def _format_money(value: int | float | None) -> str:
        if not value or value <= 0: return "н/д"
        return f"${int(value) // 1_000_000}M"

    @classmethod
    def _format_date(cls, date_str: str | None) -> str:
        if not date_str or len(date_str) < 10: return ""
        try:
            y, m, d = date_str.split("-")
            return f"{int(d)} {cls._RU_MONTHS.get(int(m), '')} {y}"
        except:
            return date_str

    @staticmethod
    def _smart_truncate(text: str, max_len: int) -> str:
        if len(text) <= max_len:
            return text
        return text[:max_len - 3].strip() + "..."

    # --- ГЛАВНЫЙ МЕТОД ---
    @classmethod
    def get_card_package(
        cls, 
        raw_data: dict, 
        media_type: str, 
        user_status: str | None = None, 
        is_full: bool = False,
        recommendations: list = None,
        user_rating: int | None = None
    ) -> dict:
        
        # --- БЕЗОПАСНЫЙ ПАРСИНГ МАССИВОВ ---
        # Спасает от квадратных скобок, если БД вернула список как строку "['Текст']"
        def parse_list(val):
            if isinstance(val, list): return val
            if isinstance(val, str):
                import ast
                try:
                    res = ast.literal_eval(val)
                    if isinstance(res, list): return res
                except:
                    cleaned = val.replace('[', '').replace(']', '').replace("'", "").replace('"', '')
                    return [x.strip() for x in cleaned.split(',') if x.strip()]
            return []

        # Актеры и режиссеры
        credits = raw_data.get("credits", {})
        if credits:
            parsed_directors = [d['name'] for d in credits.get("crew", []) if d.get('job') == 'Director']
            parsed_actors = [a['name'] for a in credits.get("cast", [])[:5]]
        else:
            parsed_directors = parse_list(raw_data.get("directors"))
            parsed_actors = parse_list(raw_data.get("actors"))
            
        # Жанры
        raw_genres = raw_data.get("genres") or raw_data.get("genre_names") or raw_data.get("genres_array") or []
        if isinstance(raw_genres, str):
            raw_genres = parse_list(raw_genres)
        parsed_genres = [g.get("name") if isinstance(g, dict) else g for g in raw_genres]
        
        # --- ГОД И СЕРИАЛЫ ---
        year_str = str(raw_data.get("year", ""))
        if not year_str or year_str == "None" or year_str == "":
            if media_type == "tv":
                start_year = str(raw_data.get("first_air_date") or "    ")[:4]
                status = raw_data.get("status", "")
                if status in ["Ended", "Canceled"]:
                    end_year = str(raw_data.get("last_air_date") or "    ")[:4]
                    year_str = f"{start_year} - {end_year}" if start_year != end_year else start_year
                else:
                    year_str = f"{start_year} - ..."
            else:
                year_str = str(raw_data.get("release_date") or "    ")[:4]

        # --- ХРОНОМЕТРАЖ ---
        runtime = raw_data.get("runtime_mins") or raw_data.get("runtime")
        if not runtime and raw_data.get("episode_run_time"):
            ert = raw_data.get("episode_run_time")
            ert_list = parse_list(ert)
            if ert_list and len(ert_list) > 0:
                try: runtime = int(ert_list[0])
                except: pass
            elif isinstance(ert, int):
                runtime = ert

        db_data = {
            "id": raw_data.get("id") or raw_data.get("movie_id"),
            "title": raw_data.get("title") or raw_data.get("name") or "Без названия",
            "year": year_str,
            "rating_numeric": raw_data.get("rating") or raw_data.get("vote_average", 0.0),
            "overview": raw_data.get("overview") or "Описание отсутствует.",
            "poster_url": raw_data.get("poster") or (cls._build_image_url(raw_data.get("poster_path"))),
            "genres_array": parsed_genres,
            "media_type": media_type,
            "runtime_mins": runtime,
            "directors": parsed_directors,
            "actors": parsed_actors,
            "studios": [s['name'] for s in raw_data.get("production_companies", [])[:2]],
            "budget": raw_data.get("budget"),
            "revenue": raw_data.get("revenue"),
            "tv_status": raw_data.get("status") or raw_data.get("tv_status"),
            "seasons": raw_data.get("number_of_seasons") or raw_data.get("seasons"),
            "recommendations": [
                {
                    "id": r.get("id") if isinstance(r, dict) else getattr(r, "movie_id", None),
                    "title": (r.get("title") or r.get("name") or "Без названия") if isinstance(r, dict) else getattr(r, "title", "Без названия")
                }
                for r in (recommendations.get("results", []) if isinstance(recommendations, dict) else (recommendations or []))
            ]
        }

        # --- ФОРМИРОВАНИЕ ВИЗУАЛА ---
        icon = "🎬" if media_type == "movie" else "📺"
        try: rating_num = float(db_data['rating_numeric'])
        except: rating_num = 0.0
        rating_str = f"⭐ {rating_num:.1f}" if rating_num else "⭐ н/д"

        meta_info = f"{icon} <b>{db_data['title']}</b> ({db_data['year']})\n"
        extra_info = ""
        post_overview = ""

        if not is_full:
            genre_short = db_data['genres_array'][0] if db_data['genres_array'] else "н/д"
            if media_type == "movie":
                time_str = f"⏱ {cls._format_runtime(db_data['runtime_mins'])}"
                meta_info += f"{rating_str} | 🎭 {genre_short} | {time_str}\n"
                if db_data['directors']:
                    meta_info += f"👤 {db_data['directors'][0]}\n"
            else:
                meta_info += f"{rating_str} | 🎭 {genre_short}\n"
                status_short = "Завершен" if db_data['tv_status'] in ["Ended", "Canceled", "Завершен"] else "Идет"
                seasons = db_data['seasons'] or "?"
                meta_info += f"📺 {seasons} сез. | 📍 {status_short}\n"
            extra_info += "\n"
            desc_limit = 180
        else:
            if media_type == "movie":
                time_str = f" | ⏱ {cls._format_runtime(db_data['runtime_mins'])}"
                meta_info += f"{rating_str}{time_str}\n"
            else:
                meta_info += f"{rating_str}\n"
                
            if db_data['genres_array']:
                meta_info += f"🎭 <b>Жанры:</b> {', '.join(db_data['genres_array'])}\n"
            
            if media_type == "movie" and db_data['directors']:
                extra_info += f"👤 <b>Режиссер:</b> {', '.join(db_data['directors'])}\n"
            elif media_type == "tv":
                tv_status_str = "📍 Завершен" if db_data['tv_status'] in ["Ended", "Canceled", "Завершен"] else "📍 Идет"
                next_ep = raw_data.get("next_episode_to_air")
                if next_ep and next_ep.get("air_date") and "Завершен" not in tv_status_str:
                    date_str = cls._format_date(next_ep.get("air_date"))
                    tv_status_str = f"📍 Идет (След. серия: {date_str})"
                seasons = db_data['seasons'] or "?"
                extra_info += f"📺 <b>Сезонов:</b> {seasons} | {tv_status_str}\n"

            extra_info += "\n📝 <b>Описание:</b>\n"
            
            post_overview = "\n\n"
            if db_data['actors']:
                post_overview += f"👥 <b>В ролях:</b> {', '.join(db_data['actors'])}\n"
            if db_data['studios']:
                post_overview += f"🏢 <b>Студии:</b> {', '.join(db_data['studios'])}\n"
            
            if media_type == "movie":
                fin = []
                if db_data.get('budget'): fin.append(f"💰 Бюджет: {cls._format_money(db_data['budget'])}")
                if db_data.get('revenue'): fin.append(f"📈 Сборы: {cls._format_money(db_data['revenue'])}")
                if fin: post_overview += " | ".join(fin) + "\n"
                
            desc_limit = 800

        footer_info = ""
        status_map = {"liked": "✅ Видел", "watchlist": "⏳ Хочу", "archive": "🗑 Архив"}
        if user_status and user_status in status_map:
            footer_info = f"\n\n📍 Статус: {status_map[user_status]}"

        RESERVE = 30
        available_space = 1024 - len(meta_info) - len(extra_info) - len(post_overview) - len(footer_info) - RESERVE
        if not is_full and available_space > desc_limit:
            available_space = desc_limit
            
        truncated_overview = cls._smart_truncate(db_data['overview'], available_space)
        caption = f"{meta_info}{extra_info}{truncated_overview}{post_overview}{footer_info}"

        return {
            "db_data": db_data,
            "caption": caption,
            "poster": db_data["poster_url"],
            "recommendations": db_data["recommendations"]
        }
