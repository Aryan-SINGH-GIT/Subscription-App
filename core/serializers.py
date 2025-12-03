from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework.validators import UniqueValidator
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError

User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        required=True,
        validators=[UniqueValidator(queryset=User.objects.all())]
    )
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    password_confirm = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'password_confirm')

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )
        
        return user

class AdminUserSerializer(serializers.ModelSerializer):
    subscription = serializers.SerializerMethodField()
    usage = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'is_active', 'date_joined', 'subscription', 'usage')

    def get_subscription(self, obj):
        from subscriptions.serializers import SubscriptionSerializer
        sub = obj.subscriptions.filter(active=True).first()
        if sub:
            return SubscriptionSerializer(sub).data
        return None

    def get_usage(self, obj):
        from metering.services import get_usage
        from subscriptions.models import PlanFeature
        
        sub = obj.subscriptions.filter(active=True).first()
        if not sub:
            return []
            
        usage_data = []
        for pf in sub.plan.planfeature_set.all():
            used = get_usage(obj.id, pf.feature.code)
            usage_data.append({
                'feature': pf.feature.name,
                'code': pf.feature.code,
                'limit': pf.limit,
                'used': used
            })
        return usage_data

class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile updates"""
    webhook_url = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'webhook_url')
        read_only_fields = ('id', 'username')  # Username cannot be changed
    
    def validate_webhook_url(self, value):
        """Validate webhook URL format"""
        if value:
            validator = URLValidator()
            try:
                validator(value)
                # Ensure it's HTTP or HTTPS
                if not value.startswith(('http://', 'https://')):
                    raise serializers.ValidationError("Webhook URL must use http:// or https://")
            except ValidationError:
                raise serializers.ValidationError("Invalid URL format")
        return value
