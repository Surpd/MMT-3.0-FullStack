import logging
from models.movie_model import MovieModel

logger = logging.getLogger(__name__)

TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

# Строгий белый список полей. Всё остальное оседает в debug-логе
KNOWN_FIELDS = {
    "id",
    "movie_id",
    "title",
    "name",
    "poster_url",
    "poster_path",
    "overview",
    "genres_array",
    "genres",
    "actors",
    "directors",
    "runtime_mins",
    "runtime",
    "episode_run_time",
    "media_type",
    "year",
    "release_date",
    "first_air_date",
    "rating_numeric",
    "vote_average",
    "reason",
}

def serialize_movie_for_webapp(movie_data: dict | MovieModel, reason: str = "") -> dict:
    """
    Единый канонический контракт выдачи фильма. 
    Принимает либо готовый объект MovieModel, либо легаси-словарь (на лету превращая его в модель).
    """
    if isinstance(movie_data, MovieModel):
        if reason:
            movie_data.reason = reason
        return movie_data.to_dict()

    # Проверка на неизвестные поля для словарей
    unknown = set(movie_data.keys()) - KNOWN_FIELDS
    if unknown:
        logger.debug(f"[SERIALIZER] Unknown fields detected: {unknown}")

    # Пропускаем через фабрику модели для жесткой очистки
    movie_obj = MovieModel.from_dict(movie_data, reason=reason)
    return movie_obj.to_dict()
