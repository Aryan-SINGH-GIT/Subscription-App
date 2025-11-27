from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

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
from .serializers import UserProfileSerializer

class UserProfileView(generics.RetrieveUpdateAPIView):
    """View for users to get and update their own profile"""
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        return self.request.user
