import base64
import uuid

from django.core.files.base import ContentFile
from rest_framework import serializers


class Base64ImageField(serializers.ImageField):

    def to_internal_value(self, encoded_image):
        is_base64_image = (
            isinstance(encoded_image, str)
            and encoded_image.startswith('data:image')
        )
        if not is_base64_image:
            return super().to_internal_value(encoded_image)

        header, encoded_file = encoded_image.split(';base64,')
        extension = header.split('/')[-1]
        file_uuid = uuid.uuid4()
        file_name = f'{file_uuid}.{extension}'
        image_file = ContentFile(
            base64.b64decode(encoded_file),
            name=file_name,
        )
        return super().to_internal_value(image_file)
