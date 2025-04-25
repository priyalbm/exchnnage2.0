from rest_framework import serializers,permissions
from django.contrib.auth import get_user_model, authenticate
from django.utils.translation import gettext_lazy as _
import re
from django.core.validators import RegexValidator
from .models import OTPVerification
import secrets
from django.utils import timezone
from plans.models import Plan
from subscriptions.models import Subscription
# from crypto_bot.models import BotConfig
from bot.models import BotConfig
from collections import defaultdict

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    """Serializer for the users object"""
    
    class Meta:
        model = User
        fields = ('id', 'email', 'password', 'username','is_active','date_joined', 'phone_number')
        extra_kwargs = {
            'password': {'write_only': True, 'min_length': 5},
            'id': {'read_only': True}
        }
    
    def validate_phone_number(self, value):
        """Validate phone number is digits only with optional + prefix"""
        if value:
            # Check if phone number follows the pattern: optional + followed by 9-15 digits
            if not re.match(r'^\+?[0-9]{9,15}$', value):
                raise serializers.ValidationError(
                    "Phone number must contain only digits with an optional '+' prefix. "
                    "Length should be between 9-15 digits."
                )
        return value
    
    def create(self, validated_data):
        """Create a new user with encrypted password and return it"""
        return User.objects.create_user(**validated_data)
    
    def update(self, instance, validated_data):
        """Update a user, setting the password correctly and return it"""
        password = validated_data.pop('password', None)
        user = super().update(instance, validated_data)
        
        if password:
            user.set_password(password)
            user.save()
        
        return user

class UserProfileSerializer(serializers.ModelSerializer):
    """Enhanced serializer for the user profile with subscription and bot data"""
    active_subscription = serializers.SerializerMethodField()
    active_bots = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'is_superuser', 'date_joined', 
                  'phone_number', 'is_active', 'active_subscription', 'active_bots')
        read_only_fields = ('id', 'email', 'date_joined')
    
    def validate_phone_number(self, value):
        """Validate phone number is digits only with optional + prefix"""
        if value:
            # Check if phone number follows the pattern: optional + followed by 9-15 digits
            if not re.match(r'^\+?[0-9]{9,15}$', value):
                raise serializers.ValidationError(
                    "Phone number must contain only digits with an optional '+' prefix. "
                    "Length should be between 9-15 digits."
                )
        return value
    
    def get_active_subscription(self, obj):
        """Get all active subscriptions grouped by exchange_id"""
        subscriptions = Subscription.objects.filter(
            user=obj, 
            status='ACTIVE'
        ).order_by('-end_date')

        if not subscriptions.exists():
            return []

        grouped_data = defaultdict(list)

        for sub in subscriptions:
            days_remaining = max(0, (sub.end_date - timezone.now()).days) if sub.end_date else 0

            subscription_data = {
                'id': sub.id,
                'plan': {
                    'id': sub.plan.id,
                    'name': sub.plan.name,
                    'price': str(sub.plan.price),  # Decimal to string
                    'duration': sub.plan.duration
                },
                'start_date': sub.start_date,
                'end_date': sub.end_date,
                'status': sub.status,
                'days_remaining': days_remaining
            }

            grouped_data[sub.plan.exchange_id].append(subscription_data)

        # Convert to list of dicts
        result = [
            {
                'exchange_id': exchange_id,
                'subscriptions': subs
            }
            for exchange_id, subs in grouped_data.items()
        ]

        return result
 
    def get_active_bots(self, obj):
        """Get the user's active bots"""
        bots = BotConfig.objects.filter(
            user=obj, 
            # is_active=True
        ).select_related('exchange')  # Changed to match your new model structure
        
        result = []
        for bot in bots:
            result.append({
                'id': bot.id,
                # 'name': bot.name,
                'exchange': {
                    'id': bot.exchange.id,
                    'name': bot.exchange.name,
                },
                'trade_volume': bot.trade_volume,
                'trading_pair': bot.pair,
                'risk_tolerance': bot.risk_tolerance,
                'status': bot.status,
                'last_run': bot.last_modified
            })
        
        return result

class AuthTokenSerializer(serializers.Serializer):
    """Serializer for user authentication object"""
    email = serializers.EmailField()
    password = serializers.CharField(
        style={'input_type': 'password'},
        trim_whitespace=False
    )
    
    def validate(self, attrs):
        """Validate and authenticate the user"""
        email = attrs.get('email')
        password = attrs.get('password')
        
        # First check if the user with this email exists
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {"email": "Email not found. Please check your email or register."},
                code='email_not_found'
            )
        
        # Now check if the password is correct
        user = authenticate(
            request=self.context.get('request'),
            username=email,
            password=password
        )
        
        if not user:
            # Since we already checked email exists, this must be a password error
            raise serializers.ValidationError(
                {"password": "Incorrect password. Please try again."},
                code='incorrect_password'
            )
        
        attrs['user'] = user
        return attrs
    
class OTPRequestSerializer(serializers.Serializer):
    """Serializer for OTP request"""
    email = serializers.EmailField()
    username = serializers.CharField(max_length=150, required=False)
    phone_number = serializers.CharField(
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
            )
        ],
        required=False
    )
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        error_messages={
            'min_length': 'Password must be at least 8 characters long.'
        }
    )

    def validate_phone_number(self, value):
        """Validate phone number format"""
        if value:
            if not re.match(r'^\+?[0-9]{9,15}$', value):
                raise serializers.ValidationError(
                    "Phone number must contain only digits with an optional '+' prefix. "
                    "Length should be between 9-15 digits."
                )
        return value

    def validate_email(self, value):
        """Check if email already exists"""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is already registered.")
        return value

class OTPVerifySerializer(serializers.Serializer):
    """Serializer for OTP verification"""
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6, min_length=6)

    def validate_otp(self, value):
        """Validate OTP format"""
        if not value.isdigit():
            raise serializers.ValidationError("OTP must be numeric.")
        return value

class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for password reset request"""
    email = serializers.EmailField()
    permission_classes = [permissions.AllowAny]

    def validate_email(self, value):
        """Check if email exists"""
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("No account is registered with this email address.")
        return value

class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for password reset confirmation"""
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6, min_length=6)
    new_password = serializers.CharField(
        write_only=True,
        min_length=8,
        error_messages={
            'min_length': 'Password must be at least 8 characters long.'
        }
    )
    confirm_new_password = serializers.CharField(
        write_only=True,
        min_length=8
    )

    def validate_otp(self, value):
        """Validate OTP format"""
        if not value.isdigit():
            raise serializers.ValidationError("OTP must be numeric.")
        return value
    
    def validate(self, data):
        """Validate that passwords match and meet complexity requirements"""
        # Check passwords match
        if data['new_password'] != data['confirm_new_password']:
            raise serializers.ValidationError({"confirm_new_password": "Passwords do not match."})
        
        # Check password complexity
        password = data['new_password']
        if len(password) < 8:
            raise serializers.ValidationError({"new_password": "Password must be at least 8 characters long."})
        
        if not re.search(r'[A-Z]', password):
            raise serializers.ValidationError({
                "new_password": "Password must contain at least one uppercase letter, one lowercase letter, one digit, one special character, and must be at least 8 characters long."
            })
        
        return data