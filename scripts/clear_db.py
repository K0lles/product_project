from products.models import Image, Product


def run() -> None:
    print('Starting database clearing...')
    Product.objects.all().delete()
    Image.objects.all().delete()
    print('Successfully deleted...')
