import base64
import hashlib
import urllib
from io import BytesIO
from typing import Type

from django.core.files import File

from products.models import ImageModelMixin, ProductModelMixin


def parse_image(image_url: str) -> BytesIO:
    response = urllib.request.urlopen(image_url)
    image_io = BytesIO(response.read())
    return image_io


def get_image_base64md5(image: BytesIO) -> str:
    return hashlib.md5(base64.b64encode(image.getvalue())).hexdigest()


def update_product_model(model: Type[ProductModelMixin], response_data: list, use_creators: bool = False) -> None:
    for item in response_data:
        product_value = item['value']
        try:
            if use_creators:
                product = model.objects.get(value=product_value, creator__isnull=True)
            else:
                product = model.objects.get(value=product_value)
            product.name = item['name']
            product.measure_date = item['measure_date']
            product.width = item['width']
            product.height = item['height']
            product.depth = item['depth']
            product.save()
        except model.DoesNotExist:
            model.objects.create(
                **item
            )


def update_image_model(model: Type[ImageModelMixin], images: list) -> None:
    for item in images:
        image_alt = item['alt']
        image_product = item['product']
        try:
            image = model.objects.get(product=image_product, alt=image_alt)
            if image.hash != item['hash']:
                image_io = parse_image(item['photo'])

                # update photo
                image_hash: str = get_image_base64md5(image_io)
                image.hash = image_hash
                image.alt = item['alt']
                image.photo.save(f'image-{item["product"]}-{image_alt}.jpg', File(image_io))
                image.save()
        except model.DoesNotExist:
            response_photo = urllib.request.urlopen(item['photo'])
            image_io = parse_image(response_photo.read())

            image_hash = get_image_base64md5(image_io)
            img_to_save = model(
                product_id=item['product'],
                alt=item['alt'],
                hash=image_hash
            )
            img_to_save.photo.save(f'image-{item["product"]}.jpg', File(image_io))
