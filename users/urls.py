from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from users.views import (
    UserViewSet,
    CustomTokenObtainPairView,
    LogoutView,
    OTPRequestView,
    OTPVerifyView,
    PasswordResetRequestView,
    PasswordResetConfirmView
)

router = DefaultRouter()
router.register(r'users', UserViewSet)

urlpatterns = [
    path('', include(router.urls)),
    
    # Authentication URLs
    path('auth/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/logout/', LogoutView.as_view(), name='auth_logout'),
    path('auth/request-otp/', OTPRequestView.as_view(), name='register-request-otp'),
    path('auth/verify-otp/', OTPVerifyView.as_view(), name='register-verify-otp'),
    
    # Password Reset URLs
    path('auth/reset-password/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('auth/reset-password/confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
]