from rest_framework import serializers
from .models import Exchange, ExchangeConfig, BotConfig, Order

class ExchangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exchange
        fields = ['id', 'name', 'code', 'base_url', 'pair_link', 'is_active']

class ExchangeConfigSerializer(serializers.ModelSerializer):
    exchange_name = serializers.ReadOnlyField(source='exchange.name')
    
    class Meta:
        model = ExchangeConfig
        fields = ['id', 'user', 'exchange', 'exchange_name', 'api_key', 'api_secret', 'base_url', 'is_active', 'created_at']
        extra_kwargs = {
            'api_secret': {'write_only': True},
            'user': {'read_only': True}
        }
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

class BotConfigSerializer(serializers.ModelSerializer):
    exchange_name = serializers.ReadOnlyField(source='exchange_config.exchange.name')
    
    class Meta:
        model = BotConfig
        fields = [
            'id', 'user', 'exchange_config', 'exchange_name', 'name', 'symbol',
            'total_order_volume', 'remaining_volume', 'per_order_volume',
            'decimal_places', 'quantity_decimal_places', 'time_interval', 'tolerance',
            'status', 'error_message', 'last_run', 'completed_volume',
            'total_orders', 'successful_orders', 'created_at', 'updated_at'
        ]
        read_only_fields = ['user', 'remaining_volume', 'status', 'error_message', 
                           'last_run', 'completed_volume', 'total_orders', 
                           'successful_orders']
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        validated_data['remaining_volume'] = validated_data['total_order_volume']
        return super().create(validated_data)

class OrderSerializer(serializers.ModelSerializer):
    bot_name = serializers.ReadOnlyField(source='bot_config.name')
    
    class Meta:
        model = Order
        fields = [
            'id', 'user', 'bot_config', 'bot_name', 'exchange_config', 'symbol',
            'order_id', 'exchange_order_id', 'side', 'order_type', 'price', 'quantity', 'filled_amount',
            'status', 'error_message', 'created_at', 'updated_at'
        ]
        read_only_fields = ['user']

class TradingPairSerializer(serializers.Serializer):
    symbol = serializers.CharField()
    baseCurrency = serializers.CharField()
    quoteCurrency = serializers.CharField()
    basePrecision = serializers.IntegerField()
    quotePrecision = serializers.IntegerField()
    minAmount = serializers.CharField(required=False)
    minTradeSize = serializers.CharField(required=False)
    symbol = serializers.CharField()
    baseCurrency = serializers.CharField()
    quoteCurrency = serializers.CharField()
    basePrecision = serializers.IntegerField()
    quotePrecision = serializers.IntegerField()
    amountPrecision = serializers.IntegerField(required=False)
    minAmount = serializers.CharField()
    minTradeSize = serializers.CharField()
    maxTradeSize = serializers.CharField(required=False)
    buyCeiling = serializers.CharField(required=False)
    sellFloor = serializers.CharField(required=False)