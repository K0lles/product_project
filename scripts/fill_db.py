import urllib
from io import BytesIO

import pandas as pd
import requests
from django.core.files import File

from product_project.settings import AUTH_TOKEN
from products.functions import get_image_base64md5
from products.models import Image, Product


def run():
    # if there are products in db, we do not fill it up
    if Product.objects.exists() or Image.objects.exists():
        print('Database is already filled.')
        return

    print('Starting filling up database...')

    print('Sending request for getting data...')
    # reading from .csv file, parsing column to pd.DataFrame
    # and making string of all barcodes separated by comma
    df: pd.DataFrame = pd.read_csv('seed/barcodes.csv')
    barcodes_to_request: str = ','.join(df['barcode'].astype(str))

    response = requests.get(f'https://ps-dev.datawiz.io/uk/api/v1/barcode/?value={barcodes_to_request}',
                            headers={
                                'Authorization': AUTH_TOKEN
                            })

    response_df = pd.DataFrame(response.json())

    images = []

    print('Getting photos from products... ')
    # put images in separate list of dictionaries, indicating in each id of product
    for index, column in response_df.iterrows():
        if column['images']:
            for image in column['images']:
                images.append({
                    'product': column['id'],
                    'photo': image['image'],
                    'alt': image['alt']
                })

    response_df.drop(columns=['images'], inplace=True)

    # creating list of Product for further bulk_create()
    print('Forming products for bulk_create()...')
    products_to_create: list = [
        Product(
            pk=row['id'],
            name=row['name'],
            value=row['value'],
            measure_date=row['measure_date'],
            width=row['width'],
            height=row['height'],
            depth=row['depth']
        )
        for i, row in response_df.iterrows()
    ]

    print('Creating products...')
    Product.objects.bulk_create(products_to_create)

    # creating list of Image for further bulk_create()
    images_to_create = []

    print('Forming photos for bulk_create()...')
    for row in images:
        response = urllib.request.urlopen(row['photo'])
        image_io = BytesIO(response.read())

        image_hash: str = get_image_base64md5(image_io)
        img_to_save = Image(
            product_id=row['product'],
            alt=row['alt'],
            hash=image_hash
        )
        img_to_save.photo.save(f'image-{row["product"]}.jpg', File(image_io))

    print('Creating images...')
    Image.objects.bulk_create(images_to_create)

    print('Finished...')
