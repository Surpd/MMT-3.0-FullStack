import os
import unittest
from unittest.mock import patch

from supabase_credentials import get_supabase_service_key


SERVICE_KEY = "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJyb2xlIjoic2VydmljZV9yb2xlIn0.x"
ANON_KEY = "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJyb2xlIjoiYW5vbiJ9.x"


class SupabaseCredentialTests(unittest.TestCase):
    def test_canonical_service_key_is_selected(self):
        with patch.dict(os.environ, {"SUPABASE_SERVICE_ROLE_KEY": SERVICE_KEY}, clear=False):
            os.environ.pop("SUPABASE_KEY", None)
            self.assertEqual(get_supabase_service_key(), SERVICE_KEY)

    def test_anon_legacy_key_is_rejected(self):
        with patch.dict(os.environ, {"SUPABASE_KEY": ANON_KEY}, clear=False):
            os.environ.pop("SUPABASE_SERVICE_ROLE_KEY", None)
            with self.assertRaisesRegex(RuntimeError, "anon/public"):
                get_supabase_service_key()

    def test_privileged_legacy_alias_remains_compatible(self):
        with patch.dict(os.environ, {"SUPABASE_KEY": SERVICE_KEY}, clear=False):
            os.environ.pop("SUPABASE_SERVICE_ROLE_KEY", None)
            self.assertEqual(get_supabase_service_key(), SERVICE_KEY)
