# -*- coding: utf-8 -*-
# Generated by Django 1.9.8 on 2016-09-19 03:44
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0162_schoolaccount'),
    ]

    operations = [
        migrations.CreateModel(
            name='PriceConfig',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('min_hours', models.PositiveIntegerField()),
                ('max_hours', models.PositiveIntegerField()),
                ('price', models.PositiveIntegerField()),
                ('deleted', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('grade', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='app.Grade')),
                ('level', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.Level')),
                ('school', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='app.School')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
