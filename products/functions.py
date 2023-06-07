import base64
import hashlib
import json
import urllib
from io import BytesIO
from typing import Type

from django.core.files import File
from django.db.models import Model

from products.models import ImageModelMixin, ProductModelMixin


def parse_image(image_url: str) -> BytesIO:
    response = urllib.request.urlopen(image_url)
    image_io = BytesIO(response.read())
    return image_io


def get_image_base64md5(image: BytesIO) -> str:
    return hashlib.md5(base64.b64encode(image.getvalue())).hexdigest()


def extract_photos_from_products(response_data: list[dict]) -> tuple[list[dict], list]:
    """
    Extracting images from fetched products data and clearing response_data
    """
    images: list = []

    for column in response_data:
        if column['images']:
            for image in column['images']:
                images.append({
                    'product': column['id'],
                    'photo': image['image'],
                    'alt': image['alt'],
                    'hash': image['base64md5']   # add hash to compare with existing in local db
                })
        del column['images']

    return response_data, images


def update_product_model(model: Type[ProductModelMixin], response_data: list, use_creators: bool = False) -> None:
    for item in response_data:
        product_value = item['value']
        try:
            if use_creators:
                product = model.objects.get(value=product_value, creator__isnull=False)
            else:
                product = model.objects.get(value=product_value)
            product.name = item['name']
            product.measure_date = item['measure_date']
            product.width = item['width']
            product.height = item['height']
            product.depth = item['depth']
            product.save()
        except model.DoesNotExist:
            if not getattr(model, 'is_remote'):
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
            if not getattr(model, 'is_remote'):
                response_photo = urllib.request.urlopen(item['photo'])
                image_io = parse_image(response_photo.read())

                image_hash = get_image_base64md5(image_io)
                img_to_save = model(
                    product_id=item['product'],
                    alt=item['alt'],
                    hash=image_hash
                )
                img_to_save.photo.save(f'image-{item["product"]}.jpg', File(image_io))


def form_cache_key(model: Type[Model], values: list[str], fields: list) -> str:
    cache_data = {
        'model_name': model.__name__,
        'values': values,
        'fields': fields,
    }
    cache_key = hashlib.sha256(json.dumps(cache_data, sort_keys=True).encode()).hexdigest()
    return cache_key
