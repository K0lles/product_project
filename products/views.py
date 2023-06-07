from typing import Type, Union

from django.db.models import Model, QuerySet
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from products.aggregators import BaseAggregator
from products.definers import ProductDefiner
from products.enums import ComparisonModelEnum
from products.models import Image, Product
from products.paginators import CustomPageNumberPagination
from products.serializers import (ProductCreateUpdateSerializer,
                                  ProductListSerializer)
from products.tasks import update_certain_images, update_certain_products


class ProductViewSet(ModelViewSet):
    serializer_class = ProductListSerializer
    pagination_class = CustomPageNumberPagination
    definer_class = ProductDefiner
    aggregator_class = BaseAggregator
    comparison_model_enum_class = ComparisonModelEnum
    lookup_field = 'value'

    def get_queryset(self) -> QuerySet[Product]:
        return Product.objects.prefetch_related('image_set').all()

    def get_my_queryset(self) -> QuerySet[Product]:
        return Product.objects.filter(creator=self.request.user)

    def get_by_value_queryset(self, model: Type[Model]) -> QuerySet[Union[Product, Image]]:
        filtration = {self.comparison_model_enum_class.get_value_field(model) + '__in': self.value}
        return model.objects.filter(**filtration)

    def get_changed_product_querysets(self, agg: BaseAggregator) -> dict[Type[Model], QuerySet]:
        queries = {}

        for model in agg.response.get('annotations').keys():

            # if there are any values filter it, otherwise get all records
            if self.value:
                value_field: str = self.comparison_model_enum_class.get_value_field(model) + '__in'
                filtering_condition = {value_field: self.value}
            else:
                filtering_condition = {}

            queries[model] = model.objects.filter(**filtering_condition)\
                .annotate(**agg.response['annotations'][model])

        return queries

    def resolve_querysets_to_response(self, query_dict: dict[Type[Model], QuerySet], agg: BaseAggregator,
                                      definer_response: dict):
        response: dict = {}
        for model, dct in definer_response.items():
            for key in dct.keys():
                auxiliary_model: Type[Model] = self.comparison_model_enum_class.get_comparison_model(model)
                auxiliary_model_name: str = auxiliary_model.__name__.lower()

                # exclude from each query not changed instances
                response[key] = query_dict[model].exclude(*agg.response['exclusions'][key])\
                    .values(
                        *self.comparison_model_enum_class.get_core_fields(model),
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
            return Product.objects.get(value=self.kwargs.get(self.lookup_field))
        except Product.DoesNotExist:
            raise ValidationError(detail={'detail': _('Не знайдено.')})

    def validate_values(self) -> None:
        # blank value is admissible
        try:
            self.value: list = self.value[0].split(',')

            for value in self.value:
                if not isinstance(value, str) and not value.isnumeric():
                    raise ValueError()

        except IndexError:
            pass

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

    @extend_schema(
        parameters=[
            OpenApiParameter(name='value', location=OpenApiParameter.QUERY,
                             description='Values', required=False, type=str),
            OpenApiParameter(name='fields', location=OpenApiParameter.QUERY,
                             description='Number of the page of the queryset that will be returned', required=True,
                             type=str)
        ]
    )
    @action(methods=['GET'], detail=False, url_path='compare')
    def get_comparison(self, request, *args, **kwargs):
        try:
            self.value = request.query_params.getlist('value')
            self.validate_values()
            fields = request.query_params.getlist('fields')[0].split(',')
            fields.sort()
        except (IndexError, AttributeError, ValueError):
            return Response({'detail': _('Перевірте правильність введених штрих-кодів та полів.')})

        definer = self.definer_class(fields)
        if definer.is_valid:
            definer_response: dict = definer.response
            agg = self.aggregator_class(definer_response)
            query_dict = self.get_changed_product_querysets(agg)
            response = self.resolve_querysets_to_response(query_dict, agg, definer_response)
            return Response(response, status=status.HTTP_200_OK)
        else:
            return Response(data=definer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        parameters=[
            OpenApiParameter(name='value', location=OpenApiParameter.QUERY, description='Values',
                             required=False, type=str),
            OpenApiParameter(name='fields', location=OpenApiParameter.QUERY,
                             description='Number of the page of the queryset that will be returned', required=True,
                             type=str)
        ]
    )
    @action(methods=['POST'], detail=False, url_path='synchronize')
    def synchronize_products_and_images(self, request, *args, **kwargs):
        try:
            self.value = request.query_params.getlist('value')
            self.validate_values()
            fields: list = request.query_params.getlist('fields')[0].split(',')
            fields.sort()
        except (IndexError, AttributeError, ValueError):
            return Response({'detail': _('Перевірте правильність вибраних штрих-кодів та полів.')})

        definer = self.definer_class(fields)
        if definer.is_valid:

            task_for_updating = {
                Product: update_certain_products,
                Image: update_certain_images
            }

            definer_response: dict = definer.response

            # set null fields for Image in order to perform update of all fields
            if Image in definer_response.keys():
                definer_response[Image] = {}

            for model in definer_response.keys():
                fields = [field for field_tuple in definer_response[model].values() for field in field_tuple]
                task_for_updating[model].delay(self.value, fields)

            return Response(data={'detail': _('Успішно оновлено.')}, status=status.HTTP_200_OK)
        else:
            return Response(data=definer.errors, status=status.HTTP_400_BAD_REQUEST)
