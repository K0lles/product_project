# Generated by Django 4.2.1 on 2023-06-02 11:36

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0005_productremote_imageremote'),
    ]

    operations = [
        migrations.AlterField(
            model_name='imageremote',
            name='product',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='products.productremote'),
        ),
    ]