from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.text import slugify
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import GoogleAuthSerializer
from .services import get_google_access_token, get_google_user_info

User = get_user_model()


def make_username(email, name):
    base = slugify(name) or slugify(email.split("@", 1)[0]) or "user"
    username = base[:150]
    suffix = 1
    while User.objects.filter(username=username).exists():
        suffix_text = str(suffix)
        username = "{}{}".format(base[: 150 - len(suffix_text)], suffix_text)
        suffix += 1
    return username


class GoogleAuthView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        access_token = get_google_access_token(serializer.validated_data["code"])
        profile = get_google_user_info(access_token)

        with transaction.atomic():
            user = User.objects.filter(email__iexact=profile["email"]).first()
            is_new_user = user is None
            if is_new_user:
                user = User(
                    email=profile["email"],
                    username=make_username(profile["email"], profile["name"]),
                )
                user.set_unusable_password()
                user.save()

        refresh = RefreshToken.for_user(user)
        refresh["email"] = user.email
        refresh["role"] = user.role
        access = refresh.access_token

        return Response(
            {
                "user": {
                    "id": user.pk,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role,
                },
                "is_new_user": is_new_user,
                "access": str(access),
                "refresh": str(refresh),
            },
            status=status.HTTP_200_OK,
        )
