---
name: mmt-recommendations
description: Improve and evaluate the My Movie Tracker recommendation engine. Use for ranking or scoring changes, rating-aware recommendations, implicit and explicit feedback signals, genre affinity, blacklist semantics, TMDB recommendation mixing, recommendation caching, deduplication, or recommendation quality tests.
---
# My Movie Tracker Recommendations
Treat recommendation behavior as core product logic.
Read:
- `docs/RECOMMENDATIONS_ENGINE.md`
- `docs/FEATURES.md`
- `docs/TECH_DEBT.md`
## Preserve understanding
Before changing scoring, reproduce the current algorithm from code.
Confirm:
- interaction loading;
- blacklist behavior;
- status weights;
- genre-affinity computation;
- recent liked seed selection;
- novice versus established-user behavior;
- TMDB sources;
- ranking;
- randomization;
- caching;
- enrichment and persistence.
## Ratings
Explicit ratings are currently stored but not used in ranking.
When adding rating-aware behavior:
- define the product semantics before coding;
- distinguish explicit rating from implicit status;
- prevent a low-rated liked item from acting like a strong positive signal;
- avoid letting one rating dominate the entire preference profile;
- preserve reasonable behavior for users with no ratings.
A sensible starting semantic model is:
- 5 stars: strong positive;
- 4 stars: positive;
- 3 stars: weak or neutral;
- 2 stars: negative;
- 1 star: strong negative.
Do not blindly hardcode these exact weights without inspecting the existing scoring scale.
## Archive/dislike semantics
Verify what `archive` means in product behavior.
Do not assume:
`remove this card == permanently dislike this content`.
If current code uses archive as both blacklist and negative preference signal, document the distinction before changing it.
## Testing
Prefer deterministic tests around:
- score ordering;
- rating influence;
- exclusion;
- duplicate prevention;
- cold-start behavior;
- conflicting signals.
Isolate randomness where practical so tests remain stable.
## Performance
Do not introduce more TMDB calls merely to improve ranking.
Prefer using already available metadata and feedback first.
Any additional external calls should have a measurable justification.
## Output
For meaningful scoring changes, explain examples such as:
- why movie A ranks above movie B;
- how a 1-star versus 5-star rating changes preference;
- how users without ratings behave.
