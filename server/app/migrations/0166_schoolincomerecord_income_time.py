# -*- coding: utf-8 -*-
# Generated by Django 1.9.8 on 2016-09-26 09:26
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0165_auto_20160919_1859'),
    ]

    operations = [
        migrations.AddField(
            model_name='schoolincomerecord',
            name='income_time',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]