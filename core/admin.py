from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import User
from subscriptions.models import Subscription
from metering.models import Invoice, MeterEvent
from metering.services import get_usage


class SubscriptionInline(admin.TabularInline):
    """Inline subscription display for User admin"""
    model = Subscription
    extra = 0
    readonly_fields = ('plan', 'start_date', 'end_date', 'active', 'subscription_actions')
    fields = ('plan', 'start_date', 'end_date', 'active', 'subscription_actions')
    can_delete = False
    
    def subscription_actions(self, obj):
        if obj.pk:
            return format_html(
                '<a href="{}" target="_blank">View Details</a>',
                reverse('admin:subscriptions_subscription_change', args=[obj.pk])
            )
        return '-'
    subscription_actions.short_description = 'Actions'


class InvoiceInline(admin.TabularInline):
    """Inline invoice display for User admin"""
    model = Invoice
    extra = 0
    readonly_fields = ('invoice_number', 'invoice_date', 'total', 'status', 'invoice_link')
    fields = ('invoice_number', 'invoice_date', 'total', 'status', 'invoice_link')
    can_delete = False
    show_change_link = True
    
    def invoice_link(self, obj):
        if obj.pk:
            return format_html(
                '<a href="{}" target="_blank">View</a>',
                reverse('admin:metering_invoice_change', args=[obj.pk])
            )
        return '-'
    invoice_link.short_description = 'Link'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.order_by('-invoice_date')[:5]  # Show only 5 most recent


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Enhanced User admin with subscription and usage information"""
    
    # Add subscription and usage info to list display
    list_display = ('username', 'email', 'subscription_info', 'usage_info', 'invoice_count', 'is_active', 'date_joined')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'date_joined')
    search_fields = ('username', 'email')
    
    # Add custom fieldsets
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Webhook Configuration', {
            'fields': ('webhook_url',)
        }),
        ('Subscription Information', {
            'fields': ('current_subscription_display', 'usage_summary_display'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('current_subscription_display', 'usage_summary_display')
    
    # Add inlines
    inlines = [SubscriptionInline, InvoiceInline]
    
    def subscription_info(self, obj):
        """Display current subscription in list view"""
        sub = obj.subscriptions.filter(active=True).first()
        if sub:
            return format_html(
                '<strong>{}</strong><br><small>₹{} / {}</small>',
                sub.plan.name,
                sub.plan.price,
                sub.plan.billing_period
            )
        return format_html('<span style="color: #999;">No subscription</span>')
    subscription_info.short_description = 'Current Subscription'
    
    def usage_info(self, obj):
        """Display usage summary in list view"""
        sub = obj.subscriptions.filter(active=True).first()
        if not sub:
            return '-'
        
        usage_items = []
        for pf in sub.plan.planfeature_set.all()[:3]:  # Show first 3 features
            used = get_usage(obj.id, pf.feature.code)
            limit_str = '∞' if pf.limit == -1 else str(pf.limit)
            usage_items.append(f'{pf.feature.name}: {used}/{limit_str}')
        
        if usage_items:
            return format_html('<br>'.join(usage_items))
        return '-'
    usage_info.short_description = 'Usage'
    
    def invoice_count(self, obj):
        """Display invoice count with link"""
        count = obj.invoices.count()
        if count > 0:
            url = reverse('admin:metering_invoice_changelist') + f'?user__id__exact={obj.id}'
            return format_html('<a href="{}">{} invoice(s)</a>', url, count)
        return '0'
    invoice_count.short_description = 'Invoices'
    
    def current_subscription_display(self, obj):
        """Display detailed subscription info in detail view"""
        if not obj.pk:
            return 'Save user first to see subscription info'
        
        sub = obj.subscriptions.filter(active=True).first()
        if not sub:
            return format_html('<p style="color: #999;">No active subscription</p>')
        
        html = f'''
        <div style="padding: 10px; background: #f5f5f5; border-radius: 5px;">
            <h4>{sub.plan.name}</h4>
            <p><strong>Price:</strong> ₹{sub.plan.price} / {sub.plan.billing_period}</p>
            <p><strong>Start Date:</strong> {sub.start_date.strftime("%Y-%m-%d %H:%M")}</p>
            <p><strong>End Date:</strong> {sub.end_date.strftime("%Y-%m-%d %H:%M") if sub.end_date else "N/A"}</p>
            <p><strong>Status:</strong> {"Active" if sub.active else "Inactive"}</p>
            <a href="/admin/subscriptions/subscription/{sub.id}/change/" class="button">Edit Subscription</a>
        </div>
        '''
        return format_html(html)
    current_subscription_display.short_description = 'Current Subscription'
    
    def usage_summary_display(self, obj):
        """Display detailed usage info in detail view"""
        if not obj.pk:
            return 'Save user first to see usage info'
        
        sub = obj.subscriptions.filter(active=True).first()
        if not sub:
            return format_html('<p style="color: #999;">No active subscription</p>')
        
        usage_items = []
        for pf in sub.plan.planfeature_set.all():
            used = get_usage(obj.id, pf.feature.code)
            limit_str = 'Unlimited' if pf.limit == -1 else str(pf.limit)
            percentage = (used / pf.limit * 100) if pf.limit != -1 else 0
            remaining = pf.limit - used if pf.limit != -1 else '∞'
            
            # Color coding based on usage
            if pf.limit != -1:
                if used >= pf.limit:
                    color = '#dc3545'  # Red
                elif percentage >= 80:
                    color = '#ffc107'  # Yellow
                else:
                    color = '#28a745'  # Green
            else:
                color = '#17a2b8'  # Blue for unlimited
            
            usage_items.append(f'''
            <div style="margin-bottom: 10px; padding: 8px; background: #fff; border-left: 3px solid {color};">
                <strong>{pf.feature.name}</strong><br>
                <small>Used: {used} / {limit_str} | Remaining: {remaining}</small>
                {f'<div style="background: #e0e0e0; height: 4px; border-radius: 2px; margin-top: 4px;"><div style="background: {color}; height: 100%; width: {min(percentage, 100)}%; border-radius: 2px;"></div></div>' if pf.limit != -1 else ''}
            </div>
            ''')
        
        if usage_items:
            html = '<div>' + ''.join(usage_items) + '</div>'
            return format_html(html)
        return format_html('<p style="color: #999;">No usage data</p>')
    usage_summary_display.short_description = 'Usage Summary'
