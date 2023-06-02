from enum import Enum
from typing import Type, Union

from django.utils.translation import gettext_lazy as _

from products.enums import ProductEnum


class BaseDefiner:
    # Enum from which we could get all fields with field type to compare
    enum_class: Type[Enum] = None

    def __init__(self, fields: Union[list, str]) -> None:
        if not self.enum_class:
            raise AttributeError(f"You did not define 'enum_class' in {self.__class__.__name__}.")

        self.fields: list = fields
        self.errors: dict = {}
        self._response = {}

        # defining fields or setting errors
        try:
            self.define_field_group()
        except KeyError:
            self.errors['detail'] = _('Перевірте правильність поля для порівняння.')

    def define_field_group(self) -> None:
        """
        Returns fields that belong to certain field type
        """
        for field in self.fields:
            if not self._response.get(self.enum_class[field].value[1], None):
                self._response[self.enum_class[field].value[1]] = [{field: self.enum_class[field].value[0]}]
                continue
            self._response[self.enum_class[field].value[1]].append({field: self.enum_class[field].value[0]})

    @property
    def is_valid(self) -> bool:
        if not self.errors:
            return True

        return False

    @property
    def response(self) -> dict:
        if self.errors:
            raise AttributeError("You couldn't get response as there are errors.")

        return self._response


class ProductDefiner(BaseDefiner):
    enum_class = ProductEnum
