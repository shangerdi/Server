# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0035_timeslot_deleted'),
    ]

    operations = [
        migrations.AddField(
            model_name='school',
            name='opened',
            field=models.BooleanField(default=False),
        ),
    ]
