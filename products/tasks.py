import datetime
import os.path
from io import BytesIO
from typing import Union

import pytz
import requests
from django.core.cache import cache

from product_project import app
from product_project.settings import AUTH_TOKEN
from products.functions import (extract_photos_from_products, form_cache_key,
                                get_image_base64md5, update_image_model,
                                update_product_model)
from products.models import Image, ImageRemote, Product, ProductRemote

kyiv_timezone = pytz.timezone('Europe/Kiev')


@app.task()
def renew_database() -> None:
    print(f'Starting updating database {datetime.datetime.now(tz=kyiv_timezone)}...')
    barcode_list: list = [str(item[0]) for item in ProductRemote.objects.all().values_list('value')]
    barcodes_to_request: str = ','.join(barcode_list)
    response_photo = requests.get(f'https://ps-dev.datawiz.io/uk/api/v1/barcode/?value={barcodes_to_request}',
                                  headers={
                                      'Authorization': AUTH_TOKEN
                                  })

    response_data: list = response_photo.json()

    response_data, images = extract_photos_from_products(response_data)

    # updating remote databases firstly
    print('Updating remote databases...')
    update_product_model(ProductRemote, response_data)
    update_image_model(ImageRemote, images)

    # updating customer's databases afterward
    print('Updating local databases...')
    update_product_model(Product, response_data, use_creators=True)
    update_image_model(Image, images)


@app.task()
def update_certain_products(product_values: Union[list[str], None], fields: list[str]) -> None:
    """
    Perform updating of certain queryset of products by indicated fields
    """

    cache_key = form_cache_key(ProductRemote, product_values, fields)
    remote_product_qs = cache.get(cache_key)

    if not product_values:
        products = Product.objects.all()
        if not remote_product_qs:
            remote_product_qs = ProductRemote.objects.all()
            cache.set(cache_key, remote_product_qs, 60 * 15)
    else:
        products = Product.objects.filter(value__in=product_values)
        if not remote_product_qs:
            remote_product_qs = ProductRemote.objects.filter(value__in=product_values)
            cache.set(cache_key, remote_product_qs, 60 * 15)

    for product in products:
        try:

            product_remote = ProductRemote.objects.get(value=product.value)
            for field in fields:
                setattr(product, field, getattr(product_remote, field))
            product.save()
        except (Product.DoesNotExist, ProductRemote.DoesNotExist):
            pass


@app.task()
def update_certain_images(product_values: Union[list[str], None], fields: list[str]) -> None:
    """
    Perform updating of certain queryset of images by all fields
    """
    if fields:
        # perform some actions if needed with certain fields
        pass

    cache_key = form_cache_key(ImageRemote, product_values, fields)
    remote_image_qs = cache.get(cache_key)

    if not product_values:
        image_queryset = Image.objects.all()
        if not remote_image_qs:
            remote_image_qs = ImageRemote.objects.select_related('product').all()
            cache.set(cache_key, remote_image_qs, 60 * 15)
    else:
        image_queryset = Image.objects.filter(product__value__in=product_values)
        if not remote_image_qs:
            remote_image_qs = ImageRemote.objects.select_related('product').filter(product__value__in=product_values)
            cache.set(cache_key, remote_image_qs, 60 * 15)

    for image in image_queryset:
        try:
            image_remote = remote_image_qs.get(alt=image.alt, product__value=image.product.value)
            image.photo.save(os.path.basename(image_remote.photo.name), image_remote.photo, save=True)
            image.alt = image_remote.alt
            image.hash = get_image_base64md5(BytesIO(image.photo.file.read()))
            image.save()
        except ImageRemote.DoesNotExist:
            pass
