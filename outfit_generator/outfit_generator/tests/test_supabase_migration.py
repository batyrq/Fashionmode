from pathlib import Path
import unittest


class SupabaseMigrationTests(unittest.TestCase):
    def setUp(self):
        self.migration = Path(__file__).resolve().parents[1] / "supabase" / "migrations" / "20260328_0001_auth_catalog_rls.sql"

    def test_migration_file_exists(self):
        self.assertTrue(self.migration.exists(), "Supabase migration file is missing")

    def test_migration_contains_auth_profile_and_rls(self):
        sql = self.migration.read_text(encoding="utf-8")

        required_fragments = [
            "create table if not exists public.profiles",
            "create trigger on_auth_user_created",
            "alter table public.profiles enable row level security",
            "create policy \"profiles_select_own\"",
            "create policy \"products_select_public\"",
            "create table if not exists public.tryon_jobs",
            "insert into storage.buckets",
            "create policy \"user_uploads_owner_write\"",
        ]

        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, sql)


if __name__ == "__main__":
    unittest.main()
