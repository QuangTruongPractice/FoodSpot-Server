# Generated by Django 5.1.6 on 2025-04-03 04:58

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('foodspots', '0003_order_ordered_date'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='order',
            name='delivery_status',
        ),
        migrations.AlterField(
            model_name='payment',
            name='order',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='payments', to='foodspots.order'),
        ),
    ]
