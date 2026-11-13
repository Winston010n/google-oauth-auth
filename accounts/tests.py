from unittest.mock import Mock, patch

import requests
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

User = get_user_model()


@override_settings(
    GOOGLE_CLIENT_ID="client-id",
    GOOGLE_CLIENT_SECRET="client-secret",
    GOOGLE_REDIRECT_URI="http://localhost:3000/auth/callback",
)
class GoogleAuthTests(APITestCase):
    url = "/api/v1/auth/google/"
    profile = {"email": "person@example.com", "name": "Example Person"}

    def mock_google_responses(self):
        token_response = Mock()
        token_response.json.return_value = {"access_token": "google-access"}
        profile_response = Mock()
        profile_response.json.return_value = self.profile
        return token_response, profile_response

    @patch("accounts.services.requests.get")
    @patch("accounts.services.requests.post")
    def test_creates_user_and_returns_jwt_claims(self, post, get):
        post_response, get_response = self.mock_google_responses()
        post.return_value = post_response
        get.return_value = get_response

        response = self.client.post(self.url, {"code": "authorization-code"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_new_user"])
        self.assertEqual(response.data["user"]["email"], self.profile["email"])
        self.assertFalse(User.objects.get().has_usable_password())

        access = AccessToken(response.data["access"])
        refresh = RefreshToken(response.data["refresh"])
        self.assertEqual(access["email"], self.profile["email"])
        self.assertEqual(access["role"], "user")
        self.assertEqual(refresh["email"], self.profile["email"])
        self.assertEqual(refresh["role"], "user")

        post.assert_called_once()
        get.assert_called_once_with(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": "Bearer google-access"},
            timeout=10,
        )

    @patch("accounts.services.requests.get")
    @patch("accounts.services.requests.post")
    def test_existing_user_is_not_duplicated(self, post, get):
        user = User.objects.create_user(
            username="existing",
            email=self.profile["email"],
            password="password",
        )
        post_response, get_response = self.mock_google_responses()
        post.return_value = post_response
        get.return_value = get_response

        response = self.client.post(self.url, {"code": "authorization-code"})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_new_user"])
        self.assertEqual(response.data["user"]["id"], user.pk)
        self.assertEqual(User.objects.count(), 1)

    @patch("accounts.services.requests.post", side_effect=requests.HTTPError("invalid code"))
    def test_google_token_error_is_401(self, _post):
        response = self.client.post(self.url, {"code": "invalid-code"})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(User.objects.count(), 0)

    @patch("accounts.services.requests.get", side_effect=requests.HTTPError("profile unavailable"))
    @patch("accounts.services.requests.post")
    def test_google_profile_error_is_401(self, post, _get):
        post_response, _ = self.mock_google_responses()
        post.return_value = post_response

        response = self.client.post(self.url, {"code": "authorization-code"})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(User.objects.count(), 0)

    def test_missing_code_is_rejected(self):
        response = self.client.post(self.url, {})

        self.assertEqual(response.status_code, 400)
