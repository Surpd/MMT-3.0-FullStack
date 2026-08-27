import asyncio
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts.backfill_metadata import _merge_missing_metadata, _needs_refresh, run


class MetadataBackfillTests(unittest.TestCase):
    def test_merge_does_not_replace_good_values_with_empty_data(self):
        existing = {"keywords": ["crime"], "directors": ["Director A"], "tmdb_vote_count": 20}
        incoming = {"keywords": [], "directors": ["Director B"], "tmdb_vote_count": None, "metadata_updated_at": "now"}
        merged = _merge_missing_metadata(existing, incoming)
        self.assertNotIn("directors", merged)
        self.assertNotIn("keywords", merged)
        self.assertNotIn("tmdb_vote_count", merged)

    def test_backfill_is_idempotently_skipped_when_required_metadata_exists(self):
        row = {"keywords": ["crime"], "directors": ["Director A"], "production_countries": ["US"],
               "tmdb_vote_count": 100, "genres_array": ["Crime"], "metadata_updated_at": "2099-01-01T00:00:00+00:00"}
        self.assertFalse(_needs_refresh(row, False))

    def test_dry_run_does_not_call_tmdb_or_write(self):
        class FakeDb:
            async def get_movies_for_backfill(self, offset=0, limit=100):
                return [{"id": 1, "media_type": "movie", "keywords": []}]

            async def update_movie_metadata(self, *_args, **_kwargs):
                raise AssertionError("dry-run must not write")

        fake_config = SimpleNamespace(db=FakeDb(), recommendation_service=None, tmdb=None)
        with patch.dict(sys.modules, {"config": fake_config}):
            report = asyncio.run(run(dry_run=True))
        self.assertEqual(report["candidates"], 1)
        self.assertEqual(report["estimated_tmdb_requests"], 1)


if __name__ == "__main__":
    unittest.main()
