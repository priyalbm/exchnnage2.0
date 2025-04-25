from rest_framework import serializers
from .models import BotConfiguration, BotTradeLog, BotPerformanceMetrics
from .validators import CoinPairValidator
from django.contrib.auth import get_user_model
User = get_user_model()

class BotConfigurationSerializer(serializers.ModelSerializer):
    # Temporary fields for API key input
    api_key = serializers.CharField(
        write_only=True, 
        required=True, 
        max_length=255
    )
    secret_key = serializers.CharField(
        write_only=True, 
        required=True, 
        max_length=255
    )

    class Meta:
        model = BotConfiguration
        fields = [
            'id','name', 'exchange', 'coin_pair', 'is_active', 
            'volume_percentage', 'strategy','max_loss_percentage', 'max_profit_percentage', 
            'api_key', 'secret_key', 'is_active','user_id',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, data):
        # Validate coin pair for the specific exchange
        try:
            CoinPairValidator.validate_coin_pair(
                data.get('exchange'), 
                data.get('coin_pair')
            )
        except ValueError as e:
            raise serializers.ValidationError({"coin_pair": str(e)})

        # Validate volume percentage
        volume_percentage = data.get('volume_percentage', 1.0)
        if volume_percentage > 100:
            raise serializers.ValidationError({
                "volume_percentage": "Volume percentage cannot exceed 100%"
            })
        
        return data

    def create(self, validated_data):
        # Remove temporary input fields
        api_key = validated_data.pop('api_key', None)
        secret_key = validated_data.pop('secret_key', None)
        
        # Create bot configuration
        bot_config = BotConfiguration.objects.create(
            **validated_data,
            api_key=api_key,
            secret_key=secret_key
        )
        
        return bot_config

    def update(self, instance, validated_data):
        # Handle API key and secret key updates
        api_key = validated_data.pop('api_key', None)
        secret_key = validated_data.pop('secret_key', None)
        
        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Update encrypted fields if provided
        if api_key:
            instance.api_key = api_key
        if secret_key:
            instance.secret_key = secret_key
        
        instance.save()
        return instance

class BotTradeLogSerializer(serializers.ModelSerializer):
    bot_config_details = serializers.SerializerMethodField()

    class Meta:
        model = BotTradeLog
        fields = '__all__'
        read_only_fields = ['id', 'timestamp']
    
    def get_bot_config_details(self, obj):
        return {
            'exchange': obj.bot_config.exchange,
            'coin_pair': obj.bot_config.coin_pair
        }

class BotPerformanceMetricsSerializer(serializers.ModelSerializer):
    bot_config_details = serializers.SerializerMethodField()

    class Meta:
        model = BotPerformanceMetrics
        fields = '__all__'
        read_only_fields = [
            'bot_config', 'total_trades', 
            'successful_trades', 'total_volume',
            'last_trading_time'
        ]
    
    def get_bot_config_details(self, obj):
        return {
            'exchange': obj.bot_config.exchange,
            'coin_pair': obj.bot_config.coin_pair,
            'is_active': obj.bot_config.is_active
        }