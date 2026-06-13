# services/tmdb.py
import asyncio
from dataclasses import dataclass
from typing import Any

import aiohttp
from utils.genres import TMDB_GENRES

TMDB_API_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

@dataclass(slots=True)
class MovieDetails:
    movie_id: int
    title: str
    year: str
    tmdb_rating: float
    overview: str
    poster_url: str
    genres: list[str]
    media_type: str = "movie"
    seasons: int | None = None

@dataclass(slots=True)
class MovieSearchResult:
    movie_id: int
    title: str
    year: str
    media_type: str = "movie"
    poster_path: str = ""

@dataclass(slots=True)
class Recommendation:
    movie_id: int
    title: str

class TMDBClient:
    def __init__(self, api_key: str, language: str = "ru-RU", timeout_sec: int = 12) -> None:
        self._api_key = api_key
        self._language = language
        self._timeout = aiohttp.ClientTimeout(total=timeout_sec)
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout, trust_env=True)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        query = {"api_key": self._api_key, "language": self._language}
        if params:
            query.update(params)

        session = await self._get_session()
        async with session.get(f"{TMDB_API_BASE}{path}", params=query) as response:
            response.raise_for_status()
            return await response.json()

    # --- Ð˜Ð¡ÐŸÐ ÐÐ’Ð›Ð•ÐÐž Ð—Ð”Ð•Ð¡Ð¬: Ð´Ð¾Ð±Ð°Ð²Ð»ÐµÐ½ Ð¿Ð°Ñ€Ð°Ð¼ÐµÑ‚Ñ€ page ---
    async def search_movies(self, query: str, page: int = 1, limit: int = 20) -> list[MovieSearchResult]:
        # ÐŸÐµÑ€ÐµÐ´Ð°ÐµÐ¼ page Ð² Ð·Ð°Ð¿Ñ€Ð¾Ñ Ðº API TMDB
        payload = await self._request("/search/multi", {"query": query, "page": page})
        results = payload.get("results") or []
        movies: list[MovieSearchResult] = []

        for item in results:
            media_type = item.get("media_type")
            if media_type not in ["movie", "tv"]:
                continue
                
            title_key = "title" if media_type == "movie" else "name"
            date_key = "release_date" if media_type == "movie" else "first_air_date"
            
            release_date = item.get(date_key) or ""
            year_val = release_date[:4] if len(release_date) >= 4 else "????"
            display_year = year_val if media_type == "movie" else f"{year_val}..."
            
            movies.append(
                MovieSearchResult(
                    movie_id=item["id"],
                    title=item.get(title_key) or "Ð‘ÐµÐ· Ð½Ð°Ð·Ð²Ð°Ð½Ð¸Ñ",
                    year=display_year,
                    media_type=media_type,
                    poster_path=item.get("poster_path") or ""
                )
            )
            if len(movies) >= limit:
                break
        return movies

    async def get_movie_details(self, movie_id: int, media_type: str = "movie") -> MovieDetails:
        path = f"/{media_type}/{movie_id}"
        payload = await self._request(path)
        
        genre_data = payload.get("genres") or []
        genres_list = [TMDB_GENRES.get(g["id"], g["name"]) for g in genre_data]

        seasons_count = None
        if media_type == "tv":
            seasons_count = payload.get("number_of_seasons")
            start_year = payload.get("first_air_date", "    ")[:4]
            status = payload.get("status", "")
            
            if status in ["Ended", "Canceled"]:
                end_year = payload.get("last_air_date", "    ")[:4]
                year = f"{start_year}-{end_year}" if start_year != end_year else start_year
            else:
                year = f"{start_year}-..."
            title_name = payload.get("name") or "Ð‘ÐµÐ· Ð½Ð°Ð·Ð²Ð°Ð½Ð¸Ñ"
        else:
            year = payload.get("release_date", "    ")[:4] or "????"
            title_name = payload.get("title") or "Ð‘ÐµÐ· Ð½Ð°Ð·Ð²Ð°Ð½Ð¸Ñ"

        vote_average = payload.get("vote_average", 0.0)

        return MovieDetails(
            movie_id=movie_id,
            title=title_name,
            year=year,
            tmdb_rating=round(float(vote_average), 1),
            overview=payload.get("overview") or "ÐžÐ¿Ð¸ÑÐ°Ð½Ð¸Ñ Ð½ÐµÑ‚.",
            poster_url=f"{TMDB_IMAGE_BASE}{payload.get('poster_path')}" if payload.get('poster_path') else "",
            genres=genres_list,
            media_type=media_type,
            seasons=seasons_count
        )
    async def get_recommendations(self, movie_id: int, media_type: str = "movie", page: int = 1) -> dict:
        path = f"/{media_type}/{movie_id}/recommendations"
        try:
            return await self._request(path, {"page": page})
        except Exception as e:
            import logging
            logging.error(f"Error fetching recommendations for {media_type} {movie_id}: {e}")
            return {}

    async def get_movie_details_extended(self, movie_id: int) -> dict:
        try:
            params = {"append_to_response": "credits,videos,images"}
            data = await self._request(f"/movie/{movie_id}", params=params)
            
            if not data:
                return {}

            credits_data = data.get("credits", {})
            cast = credits_data.get("cast", [])[:10]
            crew = credits_data.get("crew", [])
            directors = [member for member in crew if member.get("job") == "Director"]
            
            data["credits"] = {
                "cast": cast,
                "crew": directors
            }
            
            return data
        except Exception as e:
            import logging
            logging.error(f"Error fetching extended movie details: {e}")
            return {}

    async def get_tv_details_extended(self, tv_id: int) -> dict:
        try:
            params = {"append_to_response": "credits,videos,images"}
            data = await self._request(f"/tv/{tv_id}", params=params)
            
            if not data:
                return {}

            credits_data = data.get("credits", {})
            cast = credits_data.get("cast", [])[:10]
            crew = credits_data.get("crew", [])
            directors = [member for member in crew if member.get("job") == "Director"]
            
            data["credits"] = {
                "cast": cast,
                "crew": directors
            }
            
            return data
        except Exception as e:
            import logging
            logging.error(f"Error fetching extended TV details: {e}")
            return {}

    async def get_network_shows(self, network_id: int, page: int = 1) -> dict:
        try:
            params = {"with_networks": network_id, "page": page}
            data = await self._request("/discover/tv", params=params)
            return data if data else {"results": [], "total_pages": 0}
        except Exception as e:
            import logging
            logging.error(f"Error fetching shows for network: {e}")
            return {"results": [], "total_pages": 0}

    async def discover_with_filters(
        self,
        with_genres: list[int] | str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        with_companies: list[int] | None = None,
        sort_by: str = "popularity.desc",
        page: int = 1,
        media_type: str = "movie",
        **kwargs,
    ) -> dict:
        try:
            params: dict[str, Any] = {"sort_by": sort_by, "page": page}

            if with_genres:
                if isinstance(with_genres, str):
                    params["with_genres"] = with_genres
                else:
                    params["with_genres"] = ",".join(map(str, with_genres))
            if with_companies:
                params["with_companies"] = ",".join(map(str, with_companies))

            date_gte = "first_air_date.gte" if media_type == "tv" else "primary_release_date.gte"
            date_lte = "first_air_date.lte" if media_type == "tv" else "primary_release_date.lte"
            if year_from:
                params[date_gte] = f"{year_from}-01-01"
            if year_to:
                params[date_lte] = f"{year_to}-12-31"

            params.update(kwargs)

            data = await self._request(f"/discover/{media_type}", params=params)

            if not data:
                return {"results": [], "total_pages": 0, "page": page}

            results = data.get("results", []) or []
            for item in results:
                item["media_type"] = media_type

            return {
                "results": results,
                "total_pages": data.get("total_pages", 0),
                "page": data.get("page", page),
            }
        except Exception as e:
            import logging
            logging.error(f"Error in discover_with_filters ({media_type}): {e}")
            return {"results": [], "total_pages": 0, "page": page}
