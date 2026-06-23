import importlib
import os
import tempfile
import unittest


class GmailMultiAccountTokenTests(unittest.TestCase):
    def setUp(self):
        self._old_data_home = os.environ.get("VESSENCE_DATA_HOME")
        self._old_default_sender = os.environ.get("JANE_DEFAULT_GMAIL_SENDER")
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["VESSENCE_DATA_HOME"] = self.tmp.name
        os.environ.pop("JANE_DEFAULT_GMAIL_SENDER", None)

        import agent_skills.email_oauth as email_oauth

        self.email_oauth = importlib.reload(email_oauth)

    def tearDown(self):
        self.tmp.cleanup()
        if self._old_data_home is None:
            os.environ.pop("VESSENCE_DATA_HOME", None)
        else:
            os.environ["VESSENCE_DATA_HOME"] = self._old_data_home
        if self._old_default_sender is None:
            os.environ.pop("JANE_DEFAULT_GMAIL_SENDER", None)
        else:
            os.environ["JANE_DEFAULT_GMAIL_SENDER"] = self._old_default_sender

        import agent_skills.email_oauth as email_oauth

        importlib.reload(email_oauth)

    def _token(self, access_token, refresh_token):
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": 9999999999,
            "scope": "https://www.googleapis.com/auth/gmail.modify",
        }

    def test_second_account_does_not_replace_legacy_default(self):
        self.email_oauth.store_gmail_token(
            "chieh.t.wu@gmail.com",
            self._token("chieh-access", "chieh-refresh"),
        )
        self.email_oauth.store_gmail_token(
            "juliaprocess@gmail.com",
            self._token("julia-access", "julia-refresh"),
        )

        default_token = self.email_oauth.load_gmail_token()
        julia_token = self.email_oauth.load_gmail_token("juliaprocess@gmail.com")

        self.assertEqual(default_token["user_id"], "chieh.t.wu@gmail.com")
        self.assertEqual(default_token["access_token"], "chieh-access")
        self.assertEqual(julia_token["user_id"], "juliaprocess@gmail.com")
        self.assertEqual(julia_token["access_token"], "julia-access")
        self.assertEqual(
            self.email_oauth.list_gmail_token_users(),
            ["chieh.t.wu@gmail.com", "juliaprocess@gmail.com"],
        )

    def test_env_default_sender_can_select_account(self):
        self.email_oauth.store_gmail_token(
            "chieh.t.wu@gmail.com",
            self._token("chieh-access", "chieh-refresh"),
        )
        self.email_oauth.store_gmail_token(
            "juliaprocess@gmail.com",
            self._token("julia-access", "julia-refresh"),
        )

        os.environ["JANE_DEFAULT_GMAIL_SENDER"] = "juliaprocess@gmail.com"

        self.assertEqual(
            self.email_oauth.load_gmail_token()["user_id"],
            "juliaprocess@gmail.com",
        )


if __name__ == "__main__":
    unittest.main()
