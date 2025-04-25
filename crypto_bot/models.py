from django.conf import settings
from django.db import models
from django.utils import timezone

class Exchange(models.Model):
    EXCHANGE_CHOICES = [
        ('PIONEX', 'Pionex'),
        ('BINANCE', 'Binance'),
        ('KUCOIN', 'KuCoin'),
        # Add more exchanges
    ]
    
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, choices=EXCHANGE_CHOICES, unique=True, null=True)
    is_active = models.BooleanField(default=True)
    base_url = models.TextField(blank=True, null=True)
    pair_link = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

class ExchangeConfig(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    exchange = models.ForeignKey(Exchange, on_delete=models.CASCADE)
    api_key = models.CharField(max_length=255)
    api_secret = models.CharField(max_length=255)
    base_url = models.CharField(max_length=255, blank=True, null=True, help_text="Optional custom base URL")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('user', 'exchange')
    
    def __str__(self):
        return f"{self.user.username} - {self.exchange.name}"

class BotConfig(models.Model):
    STATUS_CHOICES = [
        ('idle', 'Idle'),
        ('running', 'Running'),
        ('stopped', 'Stopped'),
        ('completed', 'Completed'),
        ('error', 'Error'),
    ]
    
    # Core relationships
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    exchange_config = models.ForeignKey(ExchangeConfig, on_delete=models.CASCADE)
    
    # Bot identification
    name = models.CharField(max_length=100)
    
    # Trading pair information (from exchange API)
    symbol = models.CharField(max_length=20)  # Trading pair symbol (e.g., 'BTC_USDT')
    
    # Trading parameters
    total_order_volume = models.FloatField(help_text="Total volume to trade before bot stops")
    remaining_volume = models.FloatField(help_text="Remaining volume to trade")
    per_order_volume = models.FloatField(help_text="Volume for each individual order")
    decimal_places = models.IntegerField(default=8, help_text="Decimal places for price")
    quantity_decimal_places = models.IntegerField(default=8, help_text="Decimal places for quantity")
    
    # Timing and risk
    time_interval = models.IntegerField(default=60, help_text="Time interval between orders in seconds")
    tolerance = models.FloatField(default=1.0, help_text="Risk tolerance percentage")
    
    # Bot status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='idle')
    error_message = models.TextField(blank=True, null=True)
    last_run = models.DateTimeField(null=True, blank=True)
    
    # Statistics
    completed_volume = models.FloatField(default=0, help_text="Volume already traded")
    total_orders = models.IntegerField(default=0, help_text="Total number of orders placed")
    successful_orders = models.IntegerField(default=0, help_text="Number of successful orders")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} - {self.symbol} - {self.user.username}"
    
    def save(self, *args, **kwargs):
        # Set remaining_volume to total_order_volume when creating a new bot
        if not self.pk:
            self.remaining_volume = self.total_order_volume
        super().save(*args, **kwargs)

class Order(models.Model):
    ORDER_STATUS = [
        ('PENDING', 'Pending'),
        ('FILLED', 'Filled'),
        ('PARTIALLY_FILLED', 'Partially Filled'),
        ('CANCELED', 'Canceled'),
        ('REJECTED', 'Rejected'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    bot_config = models.ForeignKey(BotConfig, on_delete=models.SET_NULL, null=True, blank=True)
    exchange_config = models.ForeignKey(ExchangeConfig, on_delete=models.CASCADE)
    symbol = models.CharField(max_length=20)
    order_id = models.CharField(max_length=100)
    exchange_order_id = models.CharField(max_length=100, blank=True, null=True)
    side = models.CharField(max_length=10)
    order_type = models.CharField(max_length=10)
    price = models.FloatField()
    quantity = models.FloatField()
    filled_amount = models.FloatField(default=0.0)
    status = models.CharField(max_length=20, choices=ORDER_STATUS)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.symbol} - {self.side} - {self.status}"
