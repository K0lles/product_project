from rest_framework.serializers import ModelSerializer

from products.models import Image, Product


class ImageListSerializer(ModelSerializer):

    class Meta:
        model = Image
        exclude = ['product']


class ProductListSerializer(ModelSerializer):
    images = ImageListSerializer(source='image_set', many=True)

    class Meta:
        model = Product
        exclude = ['creator']


class ProductCreateUpdateSerializer(ModelSerializer):

    class Meta:
        model = Product
        exclude = ['creator']

    def create(self, validated_data: dict) -> Product:
        product = Product.objects.create(
            **validated_data,
            creator=self.context.get('user')
        )
        return product

    def update(self, instance: Product, validated_data: dict) -> Product:
        for field in validated_data.keys():
            setattr(instance, field, validated_data[field])

        instance.save()
        return instance
