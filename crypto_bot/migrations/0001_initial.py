# Generated by Django 4.2.20 on 2025-04-21 07:18

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BotConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('symbol', models.CharField(max_length=20)),
                ('total_order_volume', models.FloatField(help_text='Total volume to trade before bot stops')),
                ('remaining_volume', models.FloatField(help_text='Remaining volume to trade')),
                ('per_order_volume', models.FloatField(help_text='Volume for each individual order')),
                ('decimal_places', models.IntegerField(default=8, help_text='Decimal places for price')),
                ('quantity_decimal_places', models.IntegerField(default=8, help_text='Decimal places for quantity')),
                ('time_interval', models.IntegerField(default=60, help_text='Time interval between orders in seconds')),
                ('tolerance', models.FloatField(default=1.0, help_text='Risk tolerance percentage')),
                ('status', models.CharField(choices=[('idle', 'Idle'), ('running', 'Running'), ('stopped', 'Stopped'), ('completed', 'Completed'), ('error', 'Error')], default='idle', max_length=20)),
                ('error_message', models.TextField(blank=True, null=True)),
                ('last_run', models.DateTimeField(blank=True, null=True)),
                ('completed_volume', models.FloatField(default=0, help_text='Volume already traded')),
                ('total_orders', models.IntegerField(default=0, help_text='Total number of orders placed')),
                ('successful_orders', models.IntegerField(default=0, help_text='Number of successful orders')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='Exchange',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('code', models.CharField(choices=[('PIONEX', 'Pionex'), ('BINANCE', 'Binance'), ('KUCOIN', 'KuCoin')], max_length=20, null=True, unique=True)),
                ('is_active', models.BooleanField(default=True)),
                ('pair_link', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='ExchangeConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('api_key', models.CharField(max_length=255)),
                ('api_secret', models.CharField(max_length=255)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('exchange', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='crypto_bot.exchange')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('user', 'exchange')},
            },
        ),
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('symbol', models.CharField(max_length=20)),
                ('order_id', models.CharField(max_length=100)),
                ('side', models.CharField(max_length=10)),
                ('order_type', models.CharField(max_length=10)),
                ('price', models.FloatField()),
                ('amount', models.FloatField()),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('FILLED', 'Filled'), ('PARTIALLY_FILLED', 'Partially Filled'), ('CANCELED', 'Canceled'), ('REJECTED', 'Rejected')], max_length=20)),
                ('error_message', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('bot_config', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='crypto_bot.botconfig')),
                ('exchange_config', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='crypto_bot.exchangeconfig')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddField(
            model_name='botconfig',
            name='exchange_config',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='crypto_bot.exchangeconfig'),
        ),
        migrations.AddField(
            model_name='botconfig',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
    ]
