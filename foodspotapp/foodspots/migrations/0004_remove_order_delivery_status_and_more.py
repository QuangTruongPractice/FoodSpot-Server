# Generated by Django 5.1.6 on 2025-04-01 08:49

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('foodspots', '0003_order_ordered_date'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='order',
            name='delivery_status',
        ),
        migrations.RemoveField(
            model_name='order',
            name='ordered_date',
        ),
    ]
