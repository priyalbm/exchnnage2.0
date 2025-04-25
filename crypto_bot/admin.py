from django.contrib import admin
from .models import Exchange, ExchangeConfig, BotConfig, Order

@admin.register(Exchange)
class ExchangeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'code', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')

@admin.register(ExchangeConfig)
class ExchangeConfigAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'exchange', 'is_active', 'created_at')
    list_filter = ('is_active', 'exchange')
    search_fields = ('user__username', 'exchange__name')
    raw_id_fields = ('user',)

@admin.register(BotConfig)
class BotConfigAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'user', 'exchange_config', 'symbol', 'status')
    list_filter = ('status', 'exchange_config__exchange')
    search_fields = ('name', 'symbol', 'user__username')
    raw_id_fields = ('user', 'exchange_config')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'order_id', 'symbol', 'side', 'order_type', 'status', 'created_at')
    list_filter = ('status', 'side', 'created_at')
    search_fields = ('order_id', 'symbol', 'bot_config__name')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'