import unittest
import asyncio

from services.recommendation_service import RecommendationService
from services.cache import MemoryCache
from utils.genres import normalize_tmdb_genre


class ProfileDb:
    def __init__(self, rows, movie):
        self.rows = rows
        self.movie = movie
        self.profile = None

    async def get_user_recommendation_rows(self, _user_id):
        return self.rows

    async def get_taste_profile(self, _user_id):
        return self.profile

    async def get_movie(self, _movie_id, _media_type="movie"):
        return self.movie

    async def upsert_taste_profile(self, profile):
        self.profile = profile


class MetadataDb:
    def __init__(self):
        self.calls = 0

    async def get_movies_by_ids(self, _ids):
        self.calls += 1
        return [{"id": 123, "media_type": "movie", "keywords": ["crime"]},
                {"id": 123, "media_type": "tv", "keywords": ["mystery"]}]


class StrictFlowDb:
    async def get_user_recommendation_rows(self, _user_id):
        return [{"movie_id": 77, "status": "liked", "media_type": "movie",
                 "rating": 5, "movies": {"genre_ids": [28]}}]

    async def get_taste_profile(self, _user_id):
        return None

    async def get_movies_by_ids(self, _ids):
        return []


class RetrievalTmdb:
    def __init__(self):
        self.pages = []

    async def discover_with_filters(self, **kwargs):
        self.pages.append(kwargs)
        if kwargs.get("media_type") == "tv":
            raise RuntimeError("tv source unavailable")
        if kwargs.get("page") == 1:
            return {"results": [{"id": 1, "media_type": "movie", "vote_average": 4, "release_date": "1990-01-01"}], "total_pages": 2}
        return {"results": [{"id": 2, "media_type": "movie", "vote_average": 8.8, "vote_count": 1000, "release_date": "1995-01-01"}], "total_pages": 2}

    async def get_recommendations(self, *_args, **_kwargs):
        raise RuntimeError("similar source unavailable")


class DeepStrictTmdb:
    def __init__(self):
        self.calls = []

    async def discover_with_filters(self, **kwargs):
        self.calls.append(kwargs)
        page = kwargs["page"]
        if kwargs.get("vote_count.gte") == 300:
            return {"results": [], "total_pages": 10}
        base = page + (1000 if kwargs.get("vote_count.gte") == 100 else 2000)
        base += 3000 if kwargs.get("sort_by") == "vote_count.desc" else 0
        base += 4000 if kwargs.get("with_genres") else 0
        return {
            "results": [{"id": base, "media_type": kwargs["media_type"],
                          "vote_average": 8.7, "vote_count": 400,
                          "release_date": "2020-01-01"}],
            "total_pages": 10,
        }

    async def get_recommendations(self, *_args, **_kwargs):
        return {"results": []}


class SparsePageTmdb:
    def __init__(self):
        self.pages = []

    async def discover_with_filters(self, **kwargs):
        self.pages.append(kwargs["page"])
        return {
            "results": [{"id": kwargs["page"], "media_type": "movie",
                          "vote_average": 8.6, "vote_count": 400,
                          "release_date": f"{1990 + kwargs['page']}-01-01"}],
            "total_pages": 10,
        }


class RecommendationEngineTests(unittest.TestCase):
    def setUp(self):
        self.service = RecommendationService(None, None, None, None)

    def test_profile_is_normalized_and_recent_signal_is_retained(self):
        profile = self.service._profile_from_rows([
            *[{"status": "liked", "media_type": "movie", "movies": {"genres_array": ["Анимация"]}}] * 30,
            *[{"status": "liked", "media_type": "movie", "movies": {"genres_array": ["Детектив"]}}] * 30,
        ])
        self.assertAlmostEqual(sum(profile["genres"].values()), 1.0)
        self.assertGreater(profile["genres"]["Mystery"], profile["genres"]["Animation"])

    def test_liked_is_stronger_than_watchlist_and_profile_has_caps(self):
        old = {"status": "liked", "media_type": "movie", "rating": 5,
               "movies": {"genres_array": ["Криминал"]}}
        liked = self.service._profile_from_rows([old, {"status": "liked", "media_type": "movie", "rating": 5,
                                                        "movies": {"genres_array": ["Анимация"]}}])
        watchlist = self.service._profile_from_rows([old, {"status": "watchlist", "media_type": "movie",
                                                           "movies": {"genres_array": ["Анимация"]}}])
        self.assertGreater(liked["genres"]["Animation"], watchlist["genres"]["Animation"])
        self.assertLessEqual(len(liked["genres"]), 64)
        self.assertAlmostEqual(sum(liked["genres"].values()), 1.0)

    def test_archive_does_not_change_taste(self):
        profile = self.service._profile_from_rows([{"status": "archive", "media_type": "movie",
                                                     "movies": {"genres_array": ["Ужасы"]}}])
        self.assertEqual(profile["genres"], {})

    def test_rating_multiplier_and_repeated_likes_are_bounded(self):
        low = self.service._profile_from_rows([{"status": "liked", "rating": 1,
                                                 "movies": {"genres_array": ["Криминал"]}}])
        high = self.service._profile_from_rows([{"status": "liked", "rating": 5,
                                                  "movies": {"genres_array": ["Криминал"]}}])
        repeated = self.service._profile_from_rows([{"status": "liked", "rating": 5,
                                                      "movies": {"genres_array": ["Криминал"]}}] * 50)
        self.assertEqual(low["genres"], {})
        self.assertEqual(high["genres"], {"Crime": 1.0})
        self.assertEqual(repeated["genres"], {"Crime": 1.0})

    def test_new_interests_gradually_forget_old_interests(self):
        rows = [{"status": "liked", "movies": {"genres_array": ["Анимация"]}}]
        initial = self.service._profile_from_rows(rows)
        evolved = self.service._profile_from_rows(rows + [{"status": "liked", "movies": {"genres_array": ["Криминал"]}}] * 20)
        self.assertGreater(initial["genres"]["Animation"], evolved["genres"]["Animation"])
        self.assertGreater(evolved["genres"]["Crime"], evolved["genres"]["Animation"])

    def test_global_affinity_crosses_media_types_but_modifier_is_specific(self):
        profile = {
            "genres": {"Crime": 1.0},
            "movie_modifiers": {"genres": {"Crime": 1.0}},
            "tv_modifiers": {"genres": {}},
        }
        scored = self.service._score_candidates([
            {"id": 1, "media_type": "movie", "genre_ids": [80], "vote_average": 7, "vote_count": 1000},
            {"id": 2, "media_type": "tv", "genre_ids": [80], "vote_average": 7, "vote_count": 1000},
        ], profile["genres"], [], {}, profile)
        self.assertGreater(scored[0]["score_breakdown"]["media_modifier"], scored[1]["score_breakdown"]["media_modifier"])
        self.assertGreater(scored[1]["score_breakdown"]["genres"], 0)

    def test_tmdb_ids_use_canonical_genres(self):
        features = self.service._item_features({"genre_ids": [9648, 53]})
        self.assertEqual(set(features["genres"]), {"Mystery", "Thriller"})
        self.assertAlmostEqual(sum(features["genres"].values()), 1.0)

    def test_personal_match_beats_quality_only(self):
        profile = {"genres": {"Mystery": 1.0}, "movie_modifiers": {"genres": {}}, "tv_modifiers": {"genres": {}}}
        candidates = [
            {"id": 1, "media_type": "movie", "genre_ids": [9648], "vote_average": 7.5, "vote_count": 100},
            {"id": 2, "media_type": "movie", "genre_ids": [35], "vote_average": 9.5, "vote_count": 100000},
        ]
        ranked = sorted(self.service._score_candidates(candidates, profile["genres"], [], {}, profile),
                        key=lambda item: item["final_score"], reverse=True)
        self.assertEqual(ranked[0]["id"], 1)
        self.assertEqual(ranked[0]["reason_code"], "genres")

    def test_blacklist_keeps_movie_and_tv_identity_separate(self):
        result = self.service._filter_blacklist(
            [{"id": 10, "media_type": "movie"}, {"id": 10, "media_type": "tv"}],
            {(10, "movie")},
        )
        self.assertEqual(result, [{"id": 10, "media_type": "tv"}])

    def test_recently_shown_filter_and_versioned_cache_key_use_identity(self):
        result = self.service._filter_recently_shown(
            [{"id": 10, "media_type": "movie"}, {"id": 10, "media_type": "tv"}],
            {(10, "movie")},
        )
        self.assertEqual(result, [{"id": 10, "media_type": "tv"}])
        self.assertNotEqual(self.service._pool_key(1, "mix", None, None, None, 1),
                            self.service._pool_key(1, "mix", None, None, None, 2))

    def test_duplicate_candidates_accumulate_sources(self):
        pool = {}
        self.service._merge_candidates(pool, [{"id": 10, "media_type": "movie"}], "liked_seed")
        self.service._merge_candidates(pool, [{"id": 10, "media_type": "movie"}], "genre_discover")
        self.assertEqual(len(pool), 1)
        self.assertEqual(pool[(10, "movie")]["_sources"], ["liked_seed", "genre_discover"])

    def test_taxonomy_is_shared_with_taste_service(self):
        self.assertEqual(normalize_tmdb_genre("Детектив & Триллер"), {"Mystery": 0.5, "Thriller": 0.5})
        self.assertEqual(self.service._canonical_genre("9648"), "Mystery")

    def test_first_interaction_is_not_double_counted_when_profile_is_missing(self):
        old = {"status": "liked", "media_type": "movie", "movie_id": 1,
               "movies": {"genres_array": ["Криминал"]}}
        current = {"status": "liked", "media_type": "movie", "movie_id": 2,
                   "movies": {"genres_array": ["Детектив"]}}
        db = ProfileDb([old, current], {"id": 2, "media_type": "movie", "genres_array": ["Детектив"]})
        service = RecommendationService(db, None, None, None)

        asyncio.run(service.update_taste_profile(7, 2, "movie", "liked"))

        expected = service._profile_from_rows([old])
        features = service._item_features(db.movie)
        expected["genres"] = service._blend(expected["genres"], features["genres"], 0.09, 64)
        self.assertEqual(db.profile["genres_jsonb"], expected["genres"])
        self.assertEqual(db.profile["interaction_count"], 2)

    def test_rebuild_profile_uses_source_rows_and_increments_version(self):
        db = ProfileDb([{"status": "liked", "media_type": "tv", "rating": 5,
                         "movies": {"genres_array": ["Триллер"]}}], {})
        db.profile = {"profile_version": 4}
        service = RecommendationService(db, None, None, None)
        asyncio.run(service.rebuild_taste_profile(7))
        self.assertEqual(db.profile["profile_version"], 5)
        self.assertEqual(db.profile["genres_jsonb"], {"Thriller": 1.0})

    def test_bootstrap_repeat_replaces_snapshot_without_accumulating_taste(self):
        rows = [{"status": "liked", "media_type": "movie", "rating": 5,
                 "movies": {"genres_array": ["Криминал"]}}]
        db = ProfileDb(rows, {})
        service = RecommendationService(db, None, None, None)
        first = asyncio.run(service.bootstrap_taste_profile(7))
        second = asyncio.run(service.bootstrap_taste_profile(7))
        self.assertEqual(first["genres"], second["genres"])
        self.assertEqual(first["interaction_count"], second["interaction_count"])
        self.assertEqual(db.profile["genres_jsonb"], {"Crime": 1.0})

    def test_bucket_selection_keeps_core_adjacent_and_discovery_mix(self):
        items = [{"id": index, "media_type": "movie", "bucket": bucket, "final_score": score}
                 for index, (bucket, score) in enumerate(
                     [("core", 1.0), ("core", .9), ("core", .8), ("core", .7), ("core", .6), ("core", .5), ("core", .4),
                      ("adjacent", .39), ("adjacent", .38), ("discovery", .2), ("discovery", .1)])]
        selected = self.service._select_buckets(items, 10)
        self.assertEqual({item["bucket"] for item in selected}, {"core", "adjacent", "discovery"})
        self.assertEqual(sum(item["bucket"] == "core" for item in selected), 7)
        self.assertEqual(sum(item["bucket"] == "adjacent" for item in selected), 2)
        self.assertEqual(sum(item["bucket"] == "discovery" for item in selected), 1)

    def test_mix_interleaves_media_types_and_stays_soft(self):
        items = [{"id": index, "media_type": "movie" if index < 7 else "tv", "final_score": 1 - index / 20}
                 for index in range(10)]
        result = self.service._apply_diversity_and_protect_top(items, "mix", .70)
        self.assertEqual(sum(item["media_type"] == "movie" for item in result), 7)
        self.assertNotEqual("".join(item["media_type"][0] for item in result), "mmmmmmmttt")

    def test_strict_filters_refill_sequential_pages(self):
        tmdb = RetrievalTmdb()
        service = RecommendationService(None, tmdb, None, None)
        result = asyncio.run(service._discover_pages([], set(), "movie", 1991, None, 8.5,
                                                      pages=3, source="strict"))
        self.assertEqual([call["page"] for call in tmdb.pages], [1, 2])
        self.assertEqual([item["id"] for item in result], [2])

    def test_strict_filters_deep_refill_reaches_later_pages_and_preserves_hard_filters(self):
        tmdb = DeepStrictTmdb()
        service = RecommendationService(None, tmdb, None, None)
        result = asyncio.run(service._fetch_candidates_from_tmdb(
            ["Crime"], [], {(999999, "movie")}, "movie", 1991, 2026, 8.5,
        ))
        self.assertGreaterEqual(len(result), 10)
        self.assertTrue(all(item["vote_average"] >= 8.5 for item in result))
        self.assertTrue(all(1991 <= int(item["release_date"][:4]) <= 2026 for item in result))
        self.assertTrue(all(item["id"] != 999999 for item in result))
        self.assertGreater(max(call["page"] for call in tmdb.calls), 4)
        self.assertGreaterEqual(len(tmdb.calls), 20)
        signatures = {
            (call["media_type"], call["sort_by"], call.get("vote_count.gte"),
             tuple(call.get("with_genres") or ()), call["page"])
            for call in tmdb.calls
        }
        self.assertEqual(len(signatures), len(tmdb.calls))

    def test_strict_discovery_does_not_stop_after_one_sparse_page(self):
        tmdb = SparsePageTmdb()
        service = RecommendationService(None, tmdb, None, None)
        result = asyncio.run(service._discover_pages(
            [], set(), "movie", 1991, 2026, 8.5, pages=10, source="strict",
        ))
        self.assertEqual(tmdb.pages, list(range(1, 11)))
        self.assertEqual(len(result), 10)

    def test_sparse_strict_pool_can_relax_only_recently_shown_items(self):
        candidates = [
            {"id": 1, "media_type": "movie", "vote_average": 8.8},
            {"id": 2, "media_type": "movie", "vote_average": 8.7},
        ]
        result = self.service._fill_recently_shown_for_sparse_strict_pool(candidates, {(1, "movie")})
        self.assertEqual([item["id"] for item in result], [2, 1])

    def test_strict_retry_force_refresh_can_use_new_pages_after_shown_session(self):
        tmdb = DeepStrictTmdb()
        service = RecommendationService(
            StrictFlowDb(), tmdb, MemoryCache(3600), MemoryCache(3600),
        )
        first, _ = asyncio.run(service.get_next_movies(7, force_refresh=True,
                                                        target_type="movie", min_year=1991,
                                                        max_year=2026, min_rating=8.5))
        calls_after_first = len(tmdb.calls)
        second, _ = asyncio.run(service.get_next_movies(7, force_refresh=True,
                                                         target_type="movie", min_year=1991,
                                                         max_year=2026, min_rating=8.5))
        self.assertTrue(first)
        self.assertTrue(second)
        self.assertGreater(len(tmdb.calls), calls_after_first)
        self.assertTrue(all(item.get("vote_average", 0) >= 8.5 for item in second))

    def test_sparse_bucket_targets_never_drop_valid_filtered_candidates(self):
        items = [{"id": index, "bucket": "core", "final_score": 1 - index / 20} for index in range(10)]
        self.assertEqual(len(self.service._select_buckets(items, 10, 20)), 10)

    def test_sparse_mix_uses_available_media_type_without_quota_failure(self):
        items = [{"id": index, "media_type": "movie", "final_score": 1 - index / 20} for index in range(4)]
        result = self.service._apply_diversity_and_protect_top(items, "mix", .70)
        self.assertEqual(len(result), 4)
        self.assertTrue(all(item["media_type"] == "movie" for item in result))

    def test_deep_refill_never_relaxes_hard_filters(self):
        tmdb = RetrievalTmdb()
        service = RecommendationService(None, tmdb, None, None)
        result = asyncio.run(service._discover_pages(
            [], {(2, "movie")}, "movie", 1991, 2026, 8.5, pages=3, source="strict",
        ))
        self.assertEqual(result, [])

    def test_parallel_source_failure_does_not_drop_other_sources(self):
        tmdb = RetrievalTmdb()
        service = RecommendationService(None, tmdb, None, None)
        result = asyncio.run(service._fetch_candidates_from_tmdb([], [], set(), "mix", 1991, None, 8.5))
        self.assertIn((2, "movie"), {(item["id"], item["media_type"]) for item in result})

    def test_scoring_breakdown_contains_personal_and_quality_components(self):
        profile = {"genres": {"Mystery": 1.0}, "movie_modifiers": {"genres": {"Mystery": 1.0}}, "tv_modifiers": {}}
        item = self.service._score_candidates(
            [{"id": 1, "media_type": "movie", "genre_ids": [9648], "vote_average": 8.5, "vote_count": 10000}],
            profile["genres"], [], {}, profile,
        )[0]
        self.assertIn("taste_match", item["score_breakdown"])
        self.assertIn("quality", item["score_breakdown"])
        self.assertGreater(item["score_breakdown"]["taste_match"], 0.10 * item["score_breakdown"]["quality"])

    def test_local_metadata_join_is_one_batch_and_keeps_media_identity(self):
        db = MetadataDb()
        service = RecommendationService(db, None, None, None)
        result = asyncio.run(service._join_local_metadata([
            {"id": 123, "media_type": "movie"}, {"id": 123, "media_type": "tv"}
        ]))
        self.assertEqual(db.calls, 1)
        self.assertEqual(result[0]["keywords"], ["crime"])
        self.assertEqual(result[1]["keywords"], ["mystery"])

    def test_adaptive_mix_is_bounded(self):
        movie_heavy = [{"status": "liked", "media_type": "movie"}] * 20
        tv_heavy = [{"status": "liked", "media_type": "tv"}] * 20
        self.assertEqual(self.service._movie_ratio(movie_heavy), 0.80)
        self.assertEqual(self.service._movie_ratio(tv_heavy), 0.55)

    def test_cold_start_taste_confidence_is_gradual(self):
        self.assertEqual(self.service._taste_confidence(0), 0.0)
        self.assertGreater(self.service._taste_confidence(1), 0.0)
        self.assertLess(self.service._taste_confidence(1), self.service._taste_confidence(3))
        self.assertLess(self.service._taste_confidence(3), self.service._taste_confidence(9))
        self.assertLess(self.service._taste_confidence(9), self.service._taste_confidence(10))
        self.assertEqual(self.service._taste_confidence(20), 1.0)

    def test_cold_start_bucket_targets_are_soft_and_progressive(self):
        items = [{"id": index, "bucket": bucket, "final_score": 1 - index / 20}
                 for index, bucket in enumerate(
                     ["core"] * 7 + ["adjacent"] * 4 + ["discovery"] * 2)]
        early = self.service._select_buckets(items, 10, 2)
        forming = self.service._select_buckets(items, 10, 6)
        mature = self.service._select_buckets(items, 10, 12)
        self.assertEqual(sum(item["bucket"] == "core" for item in early), 4)
        self.assertEqual(sum(item["bucket"] == "core" for item in forming), 6)
        self.assertEqual(sum(item["bucket"] == "core" for item in mature), 7)


if __name__ == "__main__":
    unittest.main()
