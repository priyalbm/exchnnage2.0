from rest_framework import serializers
from .models import ExchangeConfig, BotConfig, BotLog, Order
from plans.models import Plan
from plans.serializers import PlanSerializer

class ExchangeConfigSerializer(serializers.ModelSerializer):
    plans = serializers.SerializerMethodField()
    lowest_price = serializers.SerializerMethodField()
    
    class Meta:
        model = ExchangeConfig
        fields = ['id', 'name', 'description', 'api_endpoint', 'pair_link', 'is_active', 'plans', 'lowest_price']
    
    def get_plans(self, obj):
        """Get all plans associated with this exchange"""
        plans = Plan.objects.filter(exchange_id=obj.id)
        return PlanSerializer(plans, many=True).data
    
    def get_lowest_price(self, obj):
        """Get the lowest price plan for this exchange"""
        plans = Plan.objects.filter(exchange_id=obj.id).order_by('price')
        if plans.exists():
            return plans.first().price
        return None

class BotConfigSerializer(serializers.ModelSerializer):
    exchange_name = serializers.CharField(source='exchange.name', read_only=True)
    
    class Meta:
        model = BotConfig
        fields = [
            'id','user_id', 'exchange', 'exchange_name', 'pair', 'api_key', 
            'secret_key', 'decimal_precision', 'risk_tolerance',
            'trade_volume', 'time_interval', 'is_active','status',
            'created_at', 'last_modified'
        ]
        extra_kwargs = {
            'api_key': {'write_only': True},
            'secret_key': {'write_only': True},
        }


class BotLogSerializer(serializers.ModelSerializer):
    bot_id = serializers.IntegerField(source='bot_config.id', read_only=True)
    
    class Meta:
        model = BotLog
        fields = ['id', 'bot_id', 'timestamp', 'level', 'message']


class OrderSerializer(serializers.ModelSerializer):
    bot_id = serializers.IntegerField(source='bot_config.id', read_only=True)
    
    class Meta:
        model = Order
        fields = [
            'id', 'bot_id', 'order_id', 'pair', 'order_type',
            'price', 'volume', 'status', 'created_at', 'updated_at'
        ]


class BotStartSerializer(serializers.Serializer):
    exchange = serializers.CharField(max_length=50)
    api_key = serializers.CharField(max_length=255)
    secret_key = serializers.CharField(max_length=255)
    pair = serializers.CharField(max_length=20)
    decimal_precision = serializers.IntegerField(default=4)
    risk_tolerance = serializers.DecimalField(max_digits=5, decimal_places=2)
    trade_volume = serializers.DecimalField(max_digits=18, decimal_places=8)
    time_interval = serializers.IntegerField(default=10)
    
    def validate_exchange(self, value):
        try:
            ExchangeConfig.objects.get(name=value.lower())
        except ExchangeConfig.DoesNotExist:
            raise serializers.ValidationError(f"Exchange '{value}' is not supported")
        return value.lower()
    
    def validate_risk_tolerance(self, value):
        if value <= 0:
            raise serializers.ValidationError("Risk tolerance must be greater than 0")
        return value
    
    def validate_trade_volume(self, value):
        if value <= 0:
            raise serializers.ValidationError("Trade volume must be greater than 0")
        return value
    
    def validate_time_interval(self, value):
        if value < 1:
            raise serializers.ValidationError("Time interval must be at least 1 second")
        return value


class BotStopSerializer(serializers.Serializer):
    bot_id = serializers.IntegerField()
    
    def validate_bot_id(self, value):
        try:
            BotConfig.objects.get(id=value)
        except BotConfig.DoesNotExist:
            raise serializers.ValidationError(f"Bot with ID {value} does not exist")
        return value
