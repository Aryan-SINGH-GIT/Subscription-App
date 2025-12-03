from rest_framework import serializers
from .models import Invoice

class InvoiceItemSerializer(serializers.Serializer):
    """Serializer for invoice line items"""
    feature = serializers.CharField()
    used = serializers.IntegerField()
    limit = serializers.IntegerField()

class InvoiceSerializer(serializers.ModelSerializer):
    """Full invoice serializer with all details"""
    username = serializers.CharField(source='user.username', read_only=True)
    plan_name = serializers.CharField(source='subscription.plan.name', read_only=True)
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'invoice_date', 'period_start', 'period_end',
            'subtotal', 'tax', 'total', 'status', 'items', 'username', 'plan_name',
            'created_at', 'updated_at', 'pdf_file'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'pdf_file']

class InvoiceListSerializer(serializers.ModelSerializer):
    """Simplified invoice serializer for list view"""
    username = serializers.CharField(source='user.username', read_only=True)
    plan_name = serializers.CharField(source='subscription.plan.name', read_only=True)
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'invoice_date', 'total', 'status',
            'username', 'plan_name', 'period_start', 'period_end'
        ]
