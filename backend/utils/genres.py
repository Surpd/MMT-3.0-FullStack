# Canonical genre taxonomy shared by profile, retrieval, scoring and UI summaries.
# TMDB_GENRES remains the display-label map used by existing cards.
TMDB_GENRES = {
    28: "Боевик",
    12: "Приключения",
    16: "Мультфильм",
    35: "Комедия",
    80: "Криминал",
    99: "Документальный",
    18: "Драма",
    10751: "Семейный",
    14: "Фэнтези",
    36: "История",
    27: "Ужасы",
    10402: "Музыка",
    9648: "Детектив",
    10749: "Мелодрама",
    878: "Фантастика",
    10770: "ТВ-фильм",
    53: "Триллер",
    10752: "Военный",
    37: "Вестерн",
    10759: "Боевик и приключения",
    10762: "Детский",
    10763: "Новости",
    10764: "Реалити-шоу",
    10765: "Фантастика и фэнтези",
    10766: "Мыльная опера",
    10767: "Ток-шоу",
}

CANONICAL_GENRES = (
    "Action", "Adventure", "Animation", "Comedy", "Crime", "Documentary", "Drama",
    "Family", "Fantasy", "History", "Horror", "Music", "Mystery", "Romance",
    "Science Fiction", "Thriller", "War", "Western", "Kids", "Reality", "News", "Talk", "Soap",
)

CANONICAL_GENRE_ALIASES = {
    "action": "Action", "боевик": "Action",
    "adventure": "Adventure", "приключения": "Adventure",
    "animation": "Animation", "анимация": "Animation", "мультфильм": "Animation",
    "comedy": "Comedy", "комедия": "Comedy",
    "crime": "Crime", "криминал": "Crime",
    "documentary": "Documentary", "документальный": "Documentary",
    "drama": "Drama", "драма": "Drama",
    "family": "Family", "семейный": "Family",
    "fantasy": "Fantasy", "фэнтези": "Fantasy",
    "history": "History", "история": "History", "исторический": "History",
    "horror": "Horror", "ужасы": "Horror",
    "music": "Music", "музыка": "Music", "музыкальный": "Music",
    "mystery": "Mystery", "детектив": "Mystery",
    "romance": "Romance", "мелодрама": "Romance", "романтика": "Romance",
    "science fiction": "Science Fiction", "sci-fi": "Science Fiction", "фантастика": "Science Fiction",
    "thriller": "Thriller", "триллер": "Thriller",
    "war": "War", "военный": "War", "война": "War",
    "western": "Western", "вестерн": "Western",
    "kids": "Kids", "детский": "Kids",
    "reality": "Reality", "реалити": "Reality",
    "news": "News", "новости": "News",
    "talk": "Talk", "ток-шоу": "Talk",
    "soap": "Soap", "мыльная опера": "Soap",
}

CANONICAL_TO_TMDB = {
    "Action": 28, "Adventure": 12, "Animation": 16, "Comedy": 35, "Crime": 80,
    "Documentary": 99, "Drama": 18, "Family": 10751, "Fantasy": 14, "History": 36,
    "Horror": 27, "Music": 10402, "Mystery": 9648, "Romance": 10749,
    "Science Fiction": 878, "Thriller": 53, "War": 10752, "Western": 37,
    "Kids": 10762, "Reality": 10764, "News": 10763, "Talk": 10767, "Soap": 10766,
}


def normalize_tmdb_genre(value: str | None) -> dict[str, float]:
    """Map one English/Russian/TMDB label to canonical genres."""
    if not isinstance(value, str):
        return {}
    label = value.strip().lower()
    if not label:
        return {}
    parts = [part.strip() for part in label.replace(" и ", "&").split("&") if part.strip()]
    share = 1.0 / len(parts) if parts else 1.0
    result: dict[str, float] = {}
    for part in parts:
        canonical = CANONICAL_GENRE_ALIASES.get(part)
        if canonical:
            result[canonical] = result.get(canonical, 0.0) + share
    return result


def normalize_title_genres(values: list[str] | None) -> dict[str, float]:
    raw: dict[str, float] = {}
    for value in values or []:
        for genre, weight in normalize_tmdb_genre(value).items():
            raw[genre] = raw.get(genre, 0.0) + weight
    total = sum(raw.values())
    return {genre: weight / total for genre, weight in raw.items()} if total else {}
