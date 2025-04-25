from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()

class BotConfiguration(models.Model):
    EXCHANGE_CHOICES = [
        ('BINANCE', 'Binance'),
        ('PIONEX', 'Pionex'),
        ('KUCOIN', 'KuCoin'),
        ('COINBASE', 'Coinbase')
    ]

    STRATEGY_CHOICES = [
        ('VOLUME_BASED', 'Volume-Based'),
        ('PRICE_RANGE', 'Price Range'),
        ('MOMENTUM', 'Momentum Trading')
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    exchange = models.CharField(max_length=20, choices=EXCHANGE_CHOICES)
    coin_pair = models.CharField(max_length=20)
    api_key = models.CharField(max_length=255)
    secret_key = models.CharField(max_length=255)
    
    # Trading Strategy Parameters
    strategy = models.CharField(max_length=20, choices=STRATEGY_CHOICES, default='VOLUME_BASED')
    volume_percentage = models.FloatField(
        default=10, 
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    
    # Tolerance Mechanism
    max_loss_percentage = models.FloatField(
        default=5, 
        validators=[MinValueValidator(0), MaxValueValidator(50)]
    )
    max_profit_percentage = models.FloatField(
        default=10, 
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.coin_pair} on {self.exchange}"

class BotTradeLog(models.Model):
    bot_config = models.ForeignKey(BotConfiguration, on_delete=models.CASCADE)
    trade_type = models.CharField(max_length=10)
    amount = models.FloatField()
    price = models.FloatField()
    status = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

class BotPerformanceMetrics(models.Model):
    bot_config = models.OneToOneField(BotConfiguration, on_delete=models.CASCADE)
    total_trades = models.IntegerField(default=0)
    successful_trades = models.IntegerField(default=0)
    total_volume = models.FloatField(default=0)
    total_profit = models.FloatField(default=0)
    total_loss = models.FloatField(default=0)
    last_trading_time = models.DateTimeField(null=True, blank=True)


# class EncryptedTextField(models.TextField):
#     """
#     Custom field to encrypt sensitive data
#     """
#     def __init__(self, *args, **kwargs):
#         # Generate a key if not provided
#         self.encryption_key = kwargs.pop('encryption_key', Fernet.generate_key())
#         super().__init__(*args, **kwargs)

#     def deconstruct(self):
#         name, path, args, kwargs = super().deconstruct()
#         kwargs['encryption_key'] = self.encryption_key
#         return name, path, args, kwargs

#     def get_prep_value(self, value):
#         if value is None:
#             return None
        
#         f = Fernet(self.encryption_key)
#         encrypted = f.encrypt(value.encode())
#         return base64.b64encode(encrypted).decode()

#     def from_db_value(self, value, expression, connection):
#         if value is None:
#             return value
        
#         try:
#             f = Fernet(self.encryption_key)
#             decrypted = f.decrypt(base64.b64decode(value))
#             return decrypted.decode()
#         except Exception:
#             return None
    # api_key = EncryptedTextField()
    # secret_key = EncryptedTextField()