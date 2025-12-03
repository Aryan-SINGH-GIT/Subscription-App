from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.utils import timezone

from rest_framework import generics
from .serializers import RegisterSerializer
from django.contrib.auth import get_user_model

User = get_user_model()

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

from rest_framework.permissions import IsAdminUser
from .serializers import AdminUserSerializer

class AdminUserListView(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminUser]

class AdminUserDetailView(generics.RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminUser]
    lookup_field = 'username'

class ApiOverview(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            "message": "Welcome to the Subscription & Entitlement Engine API",
            "endpoints": {
                "auth": {
                    "register": "/api/auth/register/",
                    "token": "/api/auth/token/",
                    "refresh": "/api/auth/token/refresh/"
                },
                "subscriptions": {
                    "plans": "/api/subscriptions/plans/",
                    "subscribe": "/api/subscriptions/subscribe/"
                },
                "metering": {
                    "event": "/api/metering/event/",
                    "summary": "/api/metering/summary/"
                },
                "admin": "/admin/"
            }
        })

from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .serializers import UserProfileSerializer
from .utils import notify_user

class UserProfileView(generics.RetrieveUpdateAPIView):
    """View for users to get and update their own profile"""
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        return self.request.user

class TestWebhookView(APIView):
    """Test webhook endpoint - sends a test webhook to user's configured URL"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user = request.user
        
        if not user.webhook_url:
            return Response(
                {"detail": "No webhook URL configured. Please set a webhook URL first."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Send test webhook
        success = notify_user(user, 'test_webhook', {
            'message': 'This is a test webhook from Subscription Engine',
            'timestamp': timezone.now().isoformat(),
            'user_id': user.id,
            'username': user.username,
            'test': True
        }, raise_on_error=False)
        
        if success:
            return Response({
                "status": "success",
                "message": "Test webhook sent successfully",
                "webhook_url": user.webhook_url
            })
        else:
            return Response(
                {"detail": "Failed to send webhook. Please check your webhook URL and try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
