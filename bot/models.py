from django.db import models
from django.utils import timezone
from django.conf import settings

class ExchangeConfig(models.Model):
    """Configuration model for supported exchanges"""
    name = models.CharField(max_length=50, unique=True)
    api_endpoint = models.URLField()
    description = models.TextField(blank=True)
    pair_link=models.URLField()
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name


class BotConfig(models.Model):
    """Configuration for a trading bot instance"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bots')
    exchange = models.ForeignKey(ExchangeConfig, on_delete=models.CASCADE)
    pair = models.CharField(max_length=20)
    api_key = models.CharField(max_length=255)
    secret_key = models.CharField(max_length=255)
    decimal_precision = models.IntegerField(default=4)
    risk_tolerance = models.DecimalField(max_digits=5, decimal_places=2)
    trade_volume = models.DecimalField(max_digits=18, decimal_places=8)
    time_interval = models.IntegerField(default=10)  # in seconds
    is_active = models.BooleanField(default=False)
    status = models.CharField(max_length=255,default='idle')
    created_at = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Bot {self.id} - {self.exchange.name}:{self.pair}"


class BotLog(models.Model):
    """Logs for bot operations"""
    bot_config = models.ForeignKey(BotConfig, on_delete=models.CASCADE, related_name='logs')
    timestamp = models.DateTimeField(default=timezone.now)
    level = models.CharField(max_length=10, choices=[
        ('DEBUG', 'Debug'),
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('CRITICAL', 'Critical'),
    ])
    message = models.TextField()
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.timestamp} | {self.level} | {self.message[:50]}"


class Order(models.Model):
    """Orders placed by the bot"""
    bot_config = models.ForeignKey(BotConfig, on_delete=models.CASCADE, related_name='orders')
    order_id = models.CharField(max_length=100)
    pair = models.CharField(max_length=20)
    order_type = models.CharField(max_length=10, choices=[
        ('BUY', 'Buy'),
        ('SELL', 'Sell'),
    ])
    price = models.DecimalField(max_digits=18, decimal_places=8)
    volume = models.DecimalField(max_digits=18, decimal_places=8)
    status = models.CharField(max_length=20, choices=[
        ('OPEN', 'Open'),
        ('FILLED', 'Filled'),
        ('CANCELED', 'Canceled'),
        ('PARTIALLY_FILLED', 'Partially Filled'),
        ('REJECTED', 'Rejected'),
    ])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.order_type} {self.pair} {self.volume} @ {self.price}"
