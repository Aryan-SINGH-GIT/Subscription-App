from rest_framework import serializers
from .models import Plan, Feature, PlanFeature, Subscription

class FeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feature
        fields = ['code', 'name', 'description']

class PlanFeatureSerializer(serializers.ModelSerializer):
    feature_code = serializers.CharField(source='feature.code')
    feature_name = serializers.CharField(source='feature.name')

    class Meta:
        model = PlanFeature
        fields = ['feature_code', 'feature_name', 'limit']

class PlanSerializer(serializers.ModelSerializer):
    features = PlanFeatureSerializer(source='planfeature_set', many=True, read_only=True)

    class Meta:
        model = Plan
        fields = [
            'id', 'name', 'price', 'billing_period', 'features',
            'overage_price', 'rate_limit', 'rate_limit_window'
        ]

class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    plan_id = serializers.PrimaryKeyRelatedField(queryset=Plan.objects.all(), source='plan', write_only=True)

    class Meta:
        model = Subscription
        fields = ['id', 'plan', 'plan_id', 'start_date', 'end_date', 'active']
        read_only_fields = ['start_date', 'end_date', 'active']
