from typing import Type

from django.db.models import Model, QuerySet
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from products.aggregators import BaseAggregator
from products.definers import ProductDefiner
from products.enums import ComparisonModelEnum
from products.models import Product
from products.paginators import CustomPageNumberPagination
from products.serializers import (ProductCreateUpdateSerializer,
                                  ProductListSerializer)
from products.tasks import update_certain_products


class ProductViewSet(ModelViewSet):
    serializer_class = ProductListSerializer
    pagination_class = CustomPageNumberPagination
    definer_class = ProductDefiner
    aggregator_class = BaseAggregator

    def get_queryset(self) -> QuerySet:
        return Product.objects.prefetch_related('image_set').all()

    def get_my_queryset(self) -> QuerySet:
        return Product.objects.filter(creator=self.request.user)

    def get_by_value_queryset(self) -> QuerySet:
        return Product.objects.filter(value__in=self.value)

    def get_changed_product_querysets(self, agg: BaseAggregator) -> dict[Type[Model], QuerySet]:
        queries = {}

        for model in agg.response.get('annotations').keys():
            value_field: str = ComparisonModelEnum.get_value_field(model) + '__in'
            queries[model] = model.objects.filter(**{value_field: self.value})\
                .annotate(**agg.response['annotations'][model])

        return queries

    def resolve_querysets_to_response(self, query_dict: dict[Type[Model], QuerySet], agg: BaseAggregator,
                                      definer_response: dict):
        response: dict = {}
        for model, dct in definer_response.items():
            for key in dct.keys():
                auxiliary_model: Type[Model] = ComparisonModelEnum.get_comparison_model(model)
                auxiliary_model_name: str = auxiliary_model.__name__.lower()

                # exclude from each query not changed instances
                response[key] = query_dict[model].exclude(*agg.response['exclusions'][key])\
                    .values(
                        *ComparisonModelEnum.get_core_fields(model),
                        *dct[key],
                        *[f'{auxiliary_model_name}__{item}' for item in dct[key]]
                )

                # deleting extra fields from list of values
                for instance in response[key]:
                    for field_name in dct[key]:
                        field_value = instance[field_name]
                        related_field_name = f'{auxiliary_model_name}__{field_name}'
                        related_field_value = instance[related_field_name]

                        if field_value == related_field_value:
                            del instance[field_name]
                            del instance[related_field_name]

                response[key] = list(response[key])

        return response

    def get_object(self):
        try:
            return Product.objects.get(pk=self.kwargs.get(self.lookup_field))
        except Product.DoesNotExist:
            raise ValidationError(detail={'detail': _('Не знайдено.')})

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        paginated_queryset = self.paginate_queryset(queryset)
        serializer = self.get_serializer(instance=paginated_queryset, many=True)
        return self.get_paginated_response(serializer.data)

    def create(self, request, *args, **kwargs):
        self.serializer_class = ProductCreateUpdateSerializer
        serializer = self.get_serializer(data=request.data, context={'user': request.user})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, *args, **kwargs):
        self.serializer_class = ProductCreateUpdateSerializer
        serializer = self.get_serializer(data=request.data, instance=self.get_object(), partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        obj: Product = self.get_object()
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(methods=['GET'], detail=False, url_path='my')
    def list_my_products(self, request, *args, **kwargs):
        queryset = self.get_my_queryset()
        paginated_queryset = self.paginate_queryset(queryset)
        serializer = self.get_serializer(instance=paginated_queryset, many=True)
        return self.get_paginated_response(serializer.data)

    @action(methods=['GET'], detail=False, url_path='compare')
    def get_comparison(self, request, *args, **kwargs):
        try:
            self.value = request.query_params.getlist('value')[0].split(',')
            fields = request.query_params.getlist('fields')[0].split(',')
        except (IndexError, AttributeError):
            return Response({'detail': _('Перевірте правильність вибраних штрих-кодів та полів.')})

        if not self.value or not fields:
            return Response({'detail': _('Укажіть поля та штрих-коди для порівняння.')})

        definer = self.definer_class(fields)
        if definer.is_valid:
            definer_response: dict = definer.response
            agg = self.aggregator_class(definer_response)
            query_dict = self.get_changed_product_querysets(agg)
            response = self.resolve_querysets_to_response(query_dict, agg, definer_response)
            return Response(response, status=status.HTTP_200_OK)
        else:
            return Response(data=definer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['POST'], detail=False, url_path='synchronize')
    def synchronize_product(self, request, *args, **kwargs):
        try:
            self.value = request.query_params.getlist('value')[0].split(',')
            fields = request.query_params.getlist('fields')[0].split(',')
        except (IndexError, AttributeError):
            return Response({'detail': _('Перевірте правильність вибраних штрих-кодів та полів.')})

        definer = self.definer_class(fields)
        if definer.is_valid:
            definer_response: dict = definer.response
            queryset_to_synchronize = self.get_by_value_queryset()
            fields_for_product = [field for field_tuple in definer_response[Product].values() for field in field_tuple]
            update_certain_products(queryset_to_synchronize, fields_for_product)
        else:
            return Response(data=definer.errors, status=status.HTTP_400_BAD_REQUEST)
