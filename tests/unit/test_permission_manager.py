import unittest
from unittest.mock import patch

from backend import permission_manager as pm


class TestPermissionManager(unittest.TestCase):
    def test_check_user_project_access_admin_has_full_access(self):
        with patch.object(pm.db, "execute_query", return_value=[{"role": "admin"}]):
            has_access, is_readonly = pm.check_user_project_access(1, 10)
            self.assertTrue(has_access)
            self.assertFalse(is_readonly)

    def test_check_user_project_access_project_owner_has_write_access(self):
        responses = [
            [{"role": "developer"}],
            [],
            [{"admin_id": 7}],
        ]

        with patch.object(pm.db, "execute_query", side_effect=responses):
            has_access, is_readonly = pm.check_user_project_access(7, 21)
            self.assertTrue(has_access)
            self.assertFalse(is_readonly)

    def test_check_user_project_access_analyzer_always_readonly(self):
        responses = [
            [{"role": "analyzer"}],
            [{"read_only": 0}],
        ]

        with patch.object(pm.db, "execute_query", side_effect=responses):
            has_access, is_readonly = pm.check_user_project_access(3, 21)
            self.assertTrue(has_access)
            self.assertTrue(is_readonly)

    def test_grant_project_permission_enforces_analyzer_readonly(self):
        responses = [
            [{"role": "admin"}],
            [{"role": "analyzer"}],
            [],
        ]

        with patch.object(pm.db, "execute_query", side_effect=responses), patch.object(pm.db, "execute_update", return_value=1) as mock_update:
            ok, message = pm.grant_project_permission(
                project_id=10,
                user_id=3,
                granted_by_id=1,
                permission_level="write",
                read_only=False,
            )

            self.assertTrue(ok)
            self.assertIn("Permission granted", message)
            args = mock_update.call_args[0][1]
            # Insert params: project_id, user_id, permission_level, read_only, granted_by_id
            self.assertEqual(args[3], True)


if __name__ == "__main__":
    unittest.main()
