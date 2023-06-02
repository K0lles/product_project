from enum import Enum

from products.models import Image, Product


class ProductEnum(Enum):
    name = (('name',), Product)
    size = (('width', 'height', 'depth'), Product)
    images = (('hash',), Image)
