from rest_framework import serializers


class GoogleAuthSerializer(serializers.Serializer):
    code = serializers.CharField(allow_blank=False, trim_whitespace=True)
