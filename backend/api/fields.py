import base64
import uuid

from django.core.files.base import ContentFile
from rest_framework import serializers


class Base64ImageField(serializers.ImageField):
    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            header, img_str = data.split(';base64,')
            ext = header.split('/')[-1]
            file_name = f'{uuid.uuid4()}.{ext}'
            data = ContentFile(base64.b64decode(img_str), name=file_name)
        return super().to_internal_value(data)