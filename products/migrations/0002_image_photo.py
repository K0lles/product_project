# Generated by Django 4.2.1 on 2023-06-01 08:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='image',
            name='photo',
            field=models.ImageField(default='null', upload_to='photo/'),
            preserve_default=False,
        ),
    ]