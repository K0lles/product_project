import pandas as pd
import requests
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from products.definers import ProductDefiner
from products.models import Product
from products.paginators import CustomPageNumberPagination
from products.serializers import (ProductCreateUpdateSerializer,
                                  ProductListSerializer)


class ProductViewSet(ModelViewSet):
    serializer_class = ProductListSerializer
    pagination_class = CustomPageNumberPagination
    definer_class = ProductDefiner

    def get_queryset(self) -> QuerySet:
        return Product.objects.prefetch_related('image_set').all()

    def get_my_queryset(self) -> QuerySet:
        return Product.objects.filter(creator=self.request.user)

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
        value = request.query_params.getlist('value')
        types = request.query_params.getlist('types')

        if not value or types:
            return Response({'detail': _('Укажіть поля та штрих-коди для порівняння.')})

        definer = self.definer_class(self.request.query_params.getlist('types'))
        if definer.is_valid:
            definer_response: dict = definer.response
            products = Product.objects.filter(value__in=value).values()
            print(definer_response)
            products_df: pd.DataFrame = pd.DataFrame(list(products))
            remote_products = requests.get(
                f'https://ps-dev.datawiz.io/uk/api/v1/barcode/?value={self.request.query_params.getlist("value")}')
            remote_products_df: pd.DataFrame = pd.DataFrame(remote_products.json())
            print(products_df)
            print(remote_products_df)
            return Response({'answer': "ok"}, status=status.HTTP_200_OK)
        else:
            return Response(data=definer.errors, status=status.HTTP_400_BAD_REQUEST)
