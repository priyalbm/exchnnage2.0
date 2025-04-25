from rest_framework import viewsets, generics, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model,authenticate
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.filters import SearchFilter
from .serializers import (
    UserSerializer,
    UserProfileSerializer,
    AuthTokenSerializer,  
    OTPRequestSerializer, 
    OTPVerifySerializer, 
    UserProfileSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer
)

from django.core.mail import send_mail
from django.conf import settings
import secrets
from .models import OTPVerification
import re

User = get_user_model()

class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow owners of an account or admins to edit it.
    """
    def has_object_permission(self, request, view, obj):
        # Admin users can access any user
        if request.user.is_superuser:
            return True
            
        # Users can only access their own profile
        return obj.id == request.user.id
    
class OTPRequestView(generics.GenericAPIView):
    """View to request OTP for registration"""
    permission_classes = [permissions.AllowAny]
    serializer_class = OTPRequestSerializer

    def generate_otp(self):
        """Generate a 6-digit OTP"""
        return secrets.randbelow(900000) + 100000  # Generates 6-digit OTP

    def send_otp_email(self, email, otp):
        """Send OTP via email"""
        subject = 'Your Registration OTP'
        message = f'Your OTP for registration is: {otp}\n\n'
        message += 'This OTP will expire in 10 minutes.'
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )

    def post(self, request):
        """Handle OTP request"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        
        # Generate and save OTP
        otp = str(self.generate_otp())
        
        # Remove any existing OTP records for this email
        OTPVerification.objects.filter(email=email).delete()
        
        # Create new OTP record
        otp_record = OTPVerification.objects.create(
            email=email,
            otp=otp
        )
        
        # Send OTP email
        self.send_otp_email(email, otp)
        
        return Response({
            'message': 'OTP sent successfully. Please check your email.',
            'email': email
        }, status=status.HTTP_200_OK)

class OTPVerifyView(generics.GenericAPIView):
    """View to verify OTP and complete registration"""
    permission_classes = [permissions.AllowAny]
    serializer_class = OTPVerifySerializer

    def post(self, request):
        """Verify OTP and register user"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        otp = serializer.validated_data['otp']
        username = request.data['username']
        password = request.data['password']
        # Find OTP record
        print(email,password,username,otp)        
        try:
            otp_record = OTPVerification.objects.get(
                email=email, 
                otp=otp, 
                is_verified=False
            )
        except OTPVerification.DoesNotExist:
            return Response({
                'error': 'Invalid OTP'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check OTP expiration
        if otp_record.is_expired():
            otp_record.delete()
            return Response({
                'error': 'OTP has expired. Please request a new OTP.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check max attempts
        if otp_record.attempts >= 3:
            otp_record.delete()
            return Response({
                'error': 'Maximum OTP verification attempts exceeded. Please request a new OTP.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Increment attempts
        otp_record.attempts += 1
        otp_record.save()
        # Extract user data from serializer
        last_name = serializer.validated_data.get('last_name', '')
        phone_number = serializer.validated_data.get('phone_number', '')
        
        if not password:
            return Response({
                'error': 'Password is required for registration.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create user
        try:
            user = User.objects.create_user(
                email=email,
                password=password,
                username=username,
                last_name=last_name,
                phone_number=phone_number
            )
        except Exception as e:
            return Response({
                'error': 'Failed to create user',
                'detail': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Mark OTP as verified
        otp_record.is_verified = True
        otp_record.save()
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'message': 'User registered successfully',
            'user': UserProfileSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)

class UserPagination(PageNumberPagination):
    page_size = 20  # Limit to 10 users per page
    page_size_query_param = 'page_size'  # Allow the client to modify the page size via the URL
    max_page_size = 100  # Optional, set a maximum limit on page size

class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom token view with user data"""
    
    def post(self, request, *args, **kwargs):
        # Check if the email exists
        email = request.data.get('email')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"error": "Email not found. Please check your email or register."},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Try to authenticate with the provided credentials
        password = request.data.get('password')
        authenticated_user = authenticate(username=email, password=password)
        
        if not authenticated_user:
            # Email exists but password is wrong
            return Response(
                {"error": "Incorrect password. Please try again."},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # If we reach here, authentication should succeed
        response = super().post(request, *args, **kwargs)
        
        # Add user details to response
        if response.status_code == 200:
            user_data = UserProfileSerializer(user).data
            response.data['user'] = user_data
            
        return response


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet for User model"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    pagination_class = UserPagination
    filter_backends = (SearchFilter,)
    search_fields = ['username', 'email']
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

    def get_permissions(self):
        """Define permissions based on action"""
        if self.action == 'create':
            permission_classes = [permissions.AllowAny]
        elif self.action == 'list':
            # Only admin users can list all users
            permission_classes = [permissions.IsAdminUser]
        else:
            # For retrieve, update, partial_update, destroy, me
            # Use the custom permission that checks ownership
            permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]
        return [permission() for permission in permission_classes]
    
    def get_serializer_class(self):
        """Return the appropriate serializer class"""
        if self.action in ['retrieve', 'me']:
            return UserProfileSerializer
        return self.serializer_class

    def get_object(self):
        """Retrieve the object and check permissions"""
        obj = super().get_object()
        # Check permissions for the object
        self.check_object_permissions(self.request, obj)
        return obj

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current authenticated user"""
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        """Create a new user"""
        # Similar to your original create method
        data = request.data
        print(data)
        if User.objects.filter(email=data.get('email')).exists():
            return Response({
                'error': 'Email already exists. Please use a different email address.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate password strength (similar to your current implementation)
        password = data.get('password')
        if not password:
            return Response({
                'error': 'Password is required.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if len(password) < 8:
            return Response({
                'error': 'Password must be at least 8 characters long.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not re.search(r'[A-Z]', password):
            return Response({
                'error': 'Password must contain at least one uppercase letter, one lowercase letter, one digit, one special character, and must be at least 8 characters long.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        user = serializer.instance
        refresh = RefreshToken.for_user(user)
        response_data = {
            'message': 'User registered successfully',
            'user': UserProfileSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }
        return Response(response_data, status=status.HTTP_201_CREATED)

    def list(self, request, *args, **kwargs):
        """Override the list method to handle search and pagination"""
        # Get the search query parameter
        search_query = request.query_params.get('search', None)
        
        # Filter users based on the search query
        if search_query:
            self.queryset = self.queryset.filter(
                username__icontains=search_query
            ) | self.queryset.filter(
                email__icontains=search_query
            )

        # Get the paginated results
        return super().list(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """Update user"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        print(request.data)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return Response({
                'error': 'Validation Error',
                'details': e.detail
            }, status=status.HTTP_400_BAD_REQUEST)
        
        self.perform_update(serializer)
        
        response_data = {
            'message': 'User updated successfully',
            'user': UserProfileSerializer(instance).data
        }
        
        return Response(response_data)
    
    def destroy(self, request, *args, **kwargs):
        """Delete user"""
        instance = self.get_object()
        self.perform_destroy(instance)
        
        return Response({
            'message': 'User deleted successfully'
        }, status=status.HTTP_200_OK)


class LogoutView(generics.GenericAPIView):
    """API view for user logout - blacklists JWT tokens"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if not refresh_token:
                return Response({
                    'error': 'Refresh token is required',
                }, status=status.HTTP_400_BAD_REQUEST)
                
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            return Response({
                'message': 'Logout successful'
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'error': 'Invalid token',
                'detail': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        

class PasswordResetRequestView(generics.GenericAPIView):
    """View to request password reset"""
    permission_classes = [permissions.AllowAny]
    serializer_class = PasswordResetRequestSerializer

    def generate_otp(self):
        """Generate a 6-digit OTP"""
        return secrets.randbelow(900000) + 100000  # Generates 6-digit OTP

    def send_reset_otp_email(self, email, otp):
        """Send password reset OTP via email"""
        subject = 'Your Password Reset OTP'
        message = f'Your OTP for password reset is: {otp}\n\n'
        message += 'This OTP will expire in 10 minutes.'
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )

    def post(self, request):
        """Handle password reset request"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        
        # Generate and save OTP
        otp = str(self.generate_otp())
        
        # Remove any existing OTP records for this email
        OTPVerification.objects.filter(email=email).delete()
        
        # Create new OTP record
        otp_record = OTPVerification.objects.create(
            email=email,
            otp=otp
        )
        
        # Send OTP email
        self.send_reset_otp_email(email, otp)
        
        return Response({
            'message': 'Password reset OTP sent. Please check your email.',
            'email': email
        }, status=status.HTTP_200_OK)


class PasswordResetConfirmView(generics.GenericAPIView):
    """View to confirm password reset with OTP"""
    permission_classes = [permissions.AllowAny]
    serializer_class = PasswordResetConfirmSerializer

    def post(self, request):
        """Reset password with OTP verification"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        otp = serializer.validated_data['otp']
        new_password = serializer.validated_data['new_password']
        
        # Find OTP record
        try:
            otp_record = OTPVerification.objects.get(
                email=email, 
                otp=otp, 
                is_verified=False
            )
        except OTPVerification.DoesNotExist:
            return Response({
                'error': 'Invalid OTP'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check OTP expiration
        if otp_record.is_expired():
            otp_record.delete()
            return Response({
                'error': 'OTP has expired. Please request a new password reset.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check max attempts
        if otp_record.attempts >= 3:
            otp_record.delete()
            return Response({
                'error': 'Maximum OTP verification attempts exceeded. Please request a new password reset.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Increment attempts
        otp_record.attempts += 1
        otp_record.save()
        
        # Get user and reset password
        try:
            user = User.objects.get(email=email)
            user.set_password(new_password)
            # Save the user with update_fields to avoid updating other fields
            user.save(update_fields=['password'])
        except User.DoesNotExist:
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Mark OTP as verified
        otp_record.is_verified = True
        otp_record.save(update_fields=['is_verified'])
        
        # Generate new tokens for the user
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'message': 'Password reset successful',
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_200_OK)