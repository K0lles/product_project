from enum import Enum
from typing import Type

from django.db.models import Model
from django.utils.translation import gettext_lazy as _

from products.models import Image, ImageRemote, Product, ProductRemote


class ProductEnum(Enum):
    name = (('name',), Product)
    size = (('width', 'height', 'depth'), Product)
    images = (('hash',), Image)


class ComparisonModelEnum(Enum):
    product = (Product, ProductRemote, ['value'])
    image = (Image, ImageRemote, ['product__value', 'alt'])

    @classmethod
    def get_comparison_model(cls, model: Type[Model]) -> Type[Model]:
        for tpl in cls:
            if tpl.value[0] == model:
                return tpl.value[1]

        raise ValueError(_('Вкажіть правильну модель.'))

    @classmethod
    def get_core_fields(cls, model: Type[Model]) -> list:
        for tpl in cls:
            if tpl.value[0] == model:
                return tpl.value[2]

        raise ValueError(_('Вкажіть правильну модель.'))

    @classmethod
    def get_value_field(cls, model: Type[Model]) -> str:
        for tpl in cls:
            if tpl.value[0] == model:
                return tpl.value[2][0]

        raise ValueError(_('Вкажіть правильну модель.'))
