from pathlib import Path
import unittest


class RecommendationMigrationTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[2]
        self.migrations = self.root / "supabase" / "migrations"

    def test_recommendation_migrations_are_present_and_ordered(self):
        versions = [
            "20260827000100_add_user_taste_profiles.sql",
            "20260827000200_add_movie_keywords.sql",
            "20260827000300_user_movies_media_identity.sql",
            "20260827000400_add_swipe_idempotency.sql",
            "20260827000500_media_typed_catalog_identity.sql",
        ]
        self.assertEqual([path.name for path in sorted(self.migrations.glob("20260827*.sql")) if path.name in versions], versions)

    def test_identity_sql_has_legacy_reconciliation_constraints_and_indexes(self):
        user_sql = (self.migrations / "20260827000300_user_movies_media_identity.sql").read_text(encoding="utf-8")
        catalog_sql = (self.migrations / "20260827000500_media_typed_catalog_identity.sql").read_text(encoding="utf-8")
        self.assertIn("from public.movies m", user_sql)
        self.assertIn("primary key (user_id, movie_id, media_type)", user_sql)
        self.assertIn("user_movies_movie_media_idx", user_sql)
        self.assertIn("primary key (id, media_type)", catalog_sql)
        self.assertIn("foreign key (movie_id, media_type)", catalog_sql)
        self.assertIn("foreign key (tv_id, media_type)", catalog_sql)
        self.assertIn("update public.tv_seasons set media_type = 'tv'", catalog_sql)
        self.assertIn("drop constraint if exists tv_seasons_tv_id_fkey", catalog_sql)

    def test_bootstrap_and_backfill_are_explicit_operations(self):
        bootstrap = (self.root / "backend" / "scripts" / "bootstrap_taste_profiles.py").read_text(encoding="utf-8")
        backfill = (self.root / "backend" / "scripts" / "backfill_metadata.py").read_text(encoding="utf-8")
        self.assertIn('parser.add_argument("--write"', bootstrap)
        self.assertIn('parser.add_argument("--write"', backfill)
        self.assertIn("_bootstrap_profile_from_rows", (self.root / "backend" / "services" / "recommendation_service.py").read_text(encoding="utf-8"))

    def test_swipe_marker_is_not_an_event_log(self):
        sql = (self.migrations / "20260827000400_add_swipe_idempotency.sql").read_text(encoding="utf-8")
        self.assertIn("last_action_id", sql)
        self.assertNotIn("create table", sql.lower())


if __name__ == "__main__":
    unittest.main()
