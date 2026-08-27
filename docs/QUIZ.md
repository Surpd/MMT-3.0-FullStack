# Quiz 2.0 runtime architecture

`QuizTab` first calls `GET /api/quiz/meta`. This is a count-only library query plus a cheap process-local Daily attempt lookup; it never creates a session, loads the global catalog, calls TMDB or composes questions. After the home screen is visible, the frontend opportunistically warms only the likely Cinema pool. A failed warmup is ignored.

## Candidate pools and indexes

`QuizPoolService` separates source data from question composition:

`source data -> bounded candidate pool -> capability/index lists -> session`

- Global pool: at most 600 recognizable local `movies` rows, shared between users and cached for 20 minutes. TMDB fallback is used only when the local pool has fewer than 12 recognizable rows, with at most one bounded discover request per media type.
- Library pool: the library gate uses `get_user_library_count` and does not transfer metadata. An unlocked session reads a rotating sample of at most 100 joined rows, cached per user for 15 minutes. Rotation plus movie/TV, rated and metadata-rich selection avoids a permanent first-page bias. The user's full library is unchanged.
- Pool preparation computes available question capabilities, same-media neighbors, people counts and personal candidate lists once. Session composition uses these indexes rather than repeatedly traversing the full catalog.
- Cache keys are distinct for `quiz_pool:global`, `quiz_pool:library:{user_id}`, `quiz_prewarm:{mode}`, `quiz_daily_questions:{date}`, and `quiz_session:{user_id}:{session_id}`. In-flight pool loads are deduplicated per process.

## Modes and Daily

- **Киноквиз** — 10 general questions.
- **Моя библиотека** — 10 questions after 20 titles, with the existing personal/general ratio.
- **Daily** — seven deterministic shared questions per date. The private question set is cached once by date; each user's attempt/session state remains separate and process-local under the current schema.

The active general types are `description_title`, `director`, `cast`, `filmography`, `release_year` and `chronology`, plus `in_library`, `not_in_library`, `my_rating` and `higher_rated` in the library mode. `poster_title` is intentionally excluded: a poster can contain the title and runtime OCR/image analysis is not acceptable. A future visual question may use only an existing backdrop/still field with a safe title-free-ish image.

## Session and answer hot path

Session creation reads the initial `user_stats` row once and stores a private snapshot in the active session. During answers, the backend reads/writes only the process-local session cache, validates the ordered question, calculates score/combo and accumulates XP/stat deltas. It does not call TMDB, read the catalog or persist stats for intermediate answers. Completion awards the existing +10 XP bonus and persists the final stats once; session deletion and an in-process per-session lock prevent replay/double-submit and duplicate completion persistence.

Scoring is unchanged: base score 100, difficulty multipliers `easy=1.0`, `medium=1.25`, `hard=1.5`, combo cap `x1.5`, speed cap 25%; wrong answers score zero and reset combo. XP remains +10 per correct answer and +10 on completion; wrong answers never reduce XP.

## Observability and media loading

Structured timing logs include `quiz_meta_ms`, `quiz_pool_global_load_ms`, `quiz_pool_library_load_ms`, `quiz_pool_index_ms`, `quiz_session_compose_ms`, `quiz_create_total_ms`, `quiz_answer_total_ms`, `quiz_completion_persist_ms` and `quiz_tmdb_fallback_count`. Logs contain timings/counts only, not library content, auth data or tokens.

The frontend fixes the selected answer immediately, disables the other options, shows a local pending spinner and uses a 12-second request timeout. Failure clears pending state and exposes an explicit retry. Question images use a lightweight skeleton and error state; a broken image does not break the session and images are requested at a bounded display size.

No schema, migration, RLS, grant, leaderboard or new product mode was added.
