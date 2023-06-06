from django.db import models

from users.models import User


class ProductModelMixin(models.Model):
    name = models.CharField(max_length=500)
    value = models.TextField(unique=True)
    measure_date = models.DateTimeField(blank=True, null=True)
    width = models.FloatField()
    height = models.FloatField()
    depth = models.FloatField()

    class Meta:
        abstract = True


class Product(ProductModelMixin):
    creator = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)


class ProductRemote(ProductModelMixin):
    pass


class ImageManager(models.Manager):
    def bulk_create(self, objs, batch_size=None, ignore_conflicts=False):
        # Validate the objects before bulk creation
        self.validate_images(objs)

        # Call the original bulk_create method
        return super().bulk_create(objs, batch_size=batch_size, ignore_conflicts=ignore_conflicts)

    def validate_images(self, objs):
        for obj in objs:
            # Check for duplicate images with the same product and alt
            if self.filter(product=obj.product, alt=obj.alt).exists():
                raise ValueError(f"Duplicate image found for product '{obj.product}' and alt '{obj.alt}'")


class ImageModelMixin(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    photo = models.ImageField(upload_to='photo/')
    alt = models.CharField(max_length=255)
    hash = models.CharField(max_length=32)

    objects = ImageManager()

    def save(self, *args, **kwargs):
        # Check if there is another Image with the same product and alt
        existing_image = self.__class__.objects.filter(product=self.product, alt=self.alt).exclude(id=self.id).first()
        if existing_image:
            raise Exception("Another image with the same product and alt already exists.")

        super().save(*args, **kwargs)

    class Meta:
        abstract = True


class Image(ImageModelMixin):
    pass


class ImageRemote(ImageModelMixin):
    product = models.ForeignKey(ProductRemote, on_delete=models.CASCADE)
