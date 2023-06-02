import datetime
import urllib

import pytz
import requests
from django.core.files import File

from product_project import app
from product_project.settings import AUTH_TOKEN
from products.functions import get_image_base64md5, parse_image
from products.models import Image, Product

kyiv_timezone = pytz.timezone('Europe/Kiev')


@app.task
def renew_database() -> None:
    print(f'Starting updating database {datetime.datetime.now(tz=kyiv_timezone)}...')
    barcode_list: list = [str(item[0]) for item in Product.objects.filter(creator__isnull=True)]
    barcodes_to_request: str = ','.join(barcode_list)
    response = requests.get(f'https://ps-dev.datawiz.io/uk/api/v1/barcode/?value={barcodes_to_request}',
                            headers={
                                'Authorization': AUTH_TOKEN
                            })

    response_data: list = response.json()

    images = []

    # put images in separate list of dictionaries, indicating in each id of product
    for column in response_data:
        if column['images']:
            for image in column['images']:
                images.append({
                    'product': column['id'],
                    'photo': image['image'],
                    'alt': image['alt'],
                    'hash': image['hash']   # add hash to compare with existing in local db
                })
        del column['images']

    for item in response_data:
        product_value = item['value']
        try:
            product = Product.objects.get(value=product_value)
            product.name = item['name']
            product.measure_date = item['measure_date']
            product.width = item['width']
            product.height = item['height']
            product.depth = item['depth']
            product.save()
        except Product.DoesNotExist:
            Product.objects.create(
                **item
            )

    for item in images:
        image_alt = item['alt']
        image_product = item['product']
        try:
            image = Image.objects.get(product=image_product, alt=image_alt)
            if image.hash != item['hash']:
                response = urllib.request.urlopen(item['photo'])
                image_io = parse_image(response.read())

                # update photo
                image_hash: str = get_image_base64md5(image_io)
                image.hash = image_hash
                image.alt = item['alt']
                image.photo.save(f'image-{item["product"]}-{image_alt}.jpg', File(image_io))
                image.save()
        except Image.DoesNotExist:
            response = urllib.request.urlopen(item['photo'])
            image_io = parse_image(response.read())

            image_hash = get_image_base64md5(image_io)
            img_to_save = Image(
                product_id=item['product'],
                alt=item['alt'],
                hash=image_hash
            )
            img_to_save.photo.save(f'image-{item["product"]}.jpg', File(image_io))
