import requests
from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USER_INFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
REQUEST_TIMEOUT = 10


def get_google_access_token(code):
    try:
        response = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise AuthenticationFailed("Не удалось обменять код Google на токен.") from exc

    if not isinstance(payload, dict):
        raise AuthenticationFailed("Google вернул некорректный ответ при обмене кода.")
    access_token = payload.get("access_token")
    if not access_token:
        raise AuthenticationFailed("Google не вернул access_token.")
    return access_token


def get_google_user_info(access_token):
    try:
        response = requests.get(
            GOOGLE_USER_INFO_URL,
            headers={"Authorization": "Bearer " + access_token},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        profile = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise AuthenticationFailed("Не удалось получить профиль пользователя Google.") from exc

    if not isinstance(profile, dict):
        raise AuthenticationFailed("Google вернул некорректный профиль пользователя.")
    email = profile.get("email")
    if not isinstance(email, str) or not email.strip():
        raise AuthenticationFailed("Google не вернул email пользователя.")

    name = profile.get("name")
    return {"email": email.strip().lower(), "name": name if isinstance(name, str) else ""}
