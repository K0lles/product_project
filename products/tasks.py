import datetime

import pytz
import requests
from django.db.models import QuerySet

from product_project import app
from product_project.settings import AUTH_TOKEN
from products.functions import update_image_model, update_product_model
from products.models import Image, ImageRemote, Product, ProductRemote

kyiv_timezone = pytz.timezone('Europe/Kiev')


@app.task
def renew_database() -> None:
    print(f'Starting updating database {datetime.datetime.now(tz=kyiv_timezone)}...')
    barcode_list: list = [str(item[0]) for item in ProductRemote.objects.all().values_list('value')]
    barcodes_to_request: str = ','.join(barcode_list)
    response_photo = requests.get(f'https://ps-dev.datawiz.io/uk/api/v1/barcode/?value={barcodes_to_request}',
                                  headers={
                                      'Authorization': AUTH_TOKEN
                                  })

    response_data: list = response_photo.json()

    images = []

    # put images in separate list of dictionaries, indicating in each id of product
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

    # updating remote databases firstly
    print('Updating remote databases...')
    update_product_model(ProductRemote, response_data)
    update_image_model(ImageRemote, images)

    # updating customer's databases afterward
    print('Updating local databases...')
    update_product_model(Product, response_data, use_creators=True)
    update_image_model(Image, images)


@app.task
def update_certain_products(products: QuerySet[Product], fields: list[str]):
    for product in products:
        try:
            product_remote = ProductRemote.objects.get(value=product.value)
            for field in fields:
                setattr(product, field, getattr(product_remote, field))
            product.save()
        except Product.DoesNotExist:
            pass
