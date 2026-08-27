# Quiz 2.0

## Architecture

Quiz uses one backend `QuizService` with a data-driven `QuestionEngine`. The engine loads one bounded batch from the local `movies` catalog and the user's `user_movies` join when needed. The frontend receives public questions; correct answers, question order, score and stats updates remain server-authoritative in process-local session state.

## Modes

- **Киноквиз** — 10 general questions about recognizable movies and TV shows.
- **Моя библиотека** — 10 questions, available from 20 library titles; the V1 composition targets six personal and four general questions. Rating questions are skipped unless at least three rating records exist.
- **Daily** — seven deterministic general questions for a calendar date, with stable order and options for all users using the same catalog snapshot.

The library gate is intentionally visible: the API returns `library_count`, `required_library_count: 20` and `remaining` instead of hiding the mode.

## Question types

V1 generators are `poster_title`, `description_title`, `director`, `cast`, `filmography`, `release_year`, `chronology`, plus `in_library`, `not_in_library`, `my_rating` and `higher_rated` for the library mode. Generators validate required metadata and skip when the answer or distractors cannot be made unambiguous. New generators belong in `backend/services/quiz_service.py` and should return the normalized `QuizQuestion` contract.

## Scoring and XP

Correct answers use base score 100, difficulty multipliers `easy=1.0`, `medium=1.25`, `hard=1.5`, a gradual combo multiplier capped at `x1.5`, and a speed bonus capped at 25%. Wrong answers score zero and reset combo. XP is separate from score: a correct answer grants 10 XP and a completed session grants 10 XP. Wrong answers never reduce points.

Existing `user_stats` fields remain the persistent stats source: `points`, `quiz_total`, `quiz_correct`, `current_streak` and `best_streak`. No database migration was added.

## V1 limitations

Quiz normally needs zero external TMDB calls when the local catalog has enough titles. If it does not, the backend makes at most one bounded discover request per media type and does not enrich each question individually. Daily attempt reservation is process-local because the current schema has no daily-attempt or leaderboard entity. Persistent Daily attempts, replay history and honest leaderboard/percentile calculations are deferred until a small, reviewed persistence design is approved.
