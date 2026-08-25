# Search

## Ordinary and TMDB search

`/api/search` caps query length at 100 characters and calls `get_search_results`. The service first checks a 10-minute in-memory cache, then handles special strings (`топ рейтинг`, `случайное кино`, `новинки 2026`), then extracts a small Russian genre/year vocabulary and calls TMDB discover. If that fails it calls TMDB `/search/multi`.

## AI fallback pipeline

`user query → Groq prompt → bounded JSON parsing → title/year/media_type extraction → parallel TMDB searches → same-year/type match → cards`.

AI is only called on page 1, only when ordinary search yields no results, and only with `GROQ_API_KEY`. That ordering avoids unnecessary LLM calls. AI output is bounded, parsed with a JSON decoder, validated for title/year/media_type and deduplicated; TMDB candidates with a requested year or media-type mismatch are rejected instead of silently taking the first popular result. Groq upstream failures are logged as AI upstream errors and safely produce an empty fallback response.

## Known behavior

The API accepts `user_id` only for validation of presence; search itself does not use user context except personalized tags. Search cache key omits user ID, which is safe for public TMDB results but not for future personalized output.
