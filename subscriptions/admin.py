from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Plan, Feature, PlanFeature, Subscription


@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    """Admin for Feature model"""
    list_display = ('code', 'name', 'description', 'plan_count')
    search_fields = ('code', 'name', 'description')
    list_filter = ('code',)
    
    def plan_count(self, obj):
        """Count how many plans include this feature"""
        count = obj.planfeature_set.count()
        if count > 0:
            url = reverse('admin:subscriptions_plan_changelist') + f'?features__id__exact={obj.id}'
            return format_html('<a href="{}">{} plan(s)</a>', url, count)
        return '0'
    plan_count.short_description = 'Plans'


class PlanFeatureInline(admin.TabularInline):
    """Inline for PlanFeature in Plan admin"""
    model = PlanFeature
    extra = 1
    fields = ('feature', 'limit')
    autocomplete_fields = ('feature',)


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    """Admin for Plan model with detailed information"""
    list_display = ('name', 'price_display', 'billing_period', 'overage_info', 'rate_limit_info', 'feature_count', 'subscription_count')
    list_filter = ('billing_period', 'overage_price')
    search_fields = ('name',)
    inlines = [PlanFeatureInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'price', 'billing_period')
        }),
        ('Billing Configuration', {
            'fields': ('overage_price',),
            'description': 'Set overage price to enable metered billing (₹0 = no overage)'
        }),
        ('Rate Limiting', {
            'fields': ('rate_limit', 'rate_limit_window'),
            'description': 'Set rate_limit > 0 to enable throttling (0 = no rate limiting)'
        }),
    )
    
    def price_display(self, obj):
        """Display price with currency"""
        return format_html('₹{}', obj.price)
    price_display.short_description = 'Price'
    
    def overage_info(self, obj):
        """Display overage billing info"""
        if obj.overage_price > 0:
            return format_html('<span style="color: #28a745;">₹{} per unit</span>', obj.overage_price)
        return format_html('<span style="color: #999;">No overage</span>')
    overage_info.short_description = 'Overage Billing'
    
    def rate_limit_info(self, obj):
        """Display rate limiting info"""
        if obj.rate_limit > 0:
            return format_html(
                '<span style="color: #ffc107;">{} calls / {}s</span>',
                obj.rate_limit,
                obj.rate_limit_window
            )
        return format_html('<span style="color: #999;">No rate limit</span>')
    rate_limit_info.short_description = 'Rate Limiting'
    
    def feature_count(self, obj):
        """Count features in plan"""
        count = obj.planfeature_set.count()
        return count
    feature_count.short_description = 'Features'
    
    def subscription_count(self, obj):
        """Count active subscriptions"""
        count = obj.subscription_set.filter(active=True).count()
        if count > 0:
            url = reverse('admin:subscriptions_subscription_changelist') + f'?plan__id__exact={obj.id}&active__exact=1'
            return format_html('<a href="{}">{} active</a>', url, count)
        return '0'
    subscription_count.short_description = 'Active Subscriptions'


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    """Admin for Subscription model"""
    list_display = ('user', 'plan', 'status_display', 'start_date', 'end_date', 'duration_info', 'quick_actions')
    list_filter = ('active', 'plan', 'start_date', 'plan__billing_period')
    search_fields = ('user__username', 'user__email', 'plan__name')
    readonly_fields = ('subscription_info', 'usage_display', 'invoice_count_display')
    date_hierarchy = 'start_date'
    
    fieldsets = (
        ('Subscription Details', {
            'fields': ('user', 'plan', 'start_date', 'end_date', 'active')
        }),
        ('Information', {
            'fields': ('subscription_info', 'usage_display', 'invoice_count_display'),
            'classes': ('collapse',)
        }),
    )
    
    def status_display(self, obj):
        """Display subscription status with color"""
        if obj.active:
            return format_html('<span style="color: #28a745; font-weight: bold;">● Active</span>')
        return format_html('<span style="color: #dc3545;">● Inactive</span>')
    status_display.short_description = 'Status'
    
    def duration_info(self, obj):
        """Display subscription duration"""
        if obj.end_date and obj.start_date:
            duration = obj.end_date - obj.start_date
            days = duration.days
            if days < 30:
                return f'{days} days'
            elif days < 365:
                return f'{days // 30} months'
            else:
                return f'{days // 365} years'
        return '-'
    duration_info.short_description = 'Duration'
    
    def quick_actions(self, obj):
        """Quick action links"""
        if obj.pk:
            links = []
            # View user
            links.append(f'<a href="/admin/core/user/{obj.user.id}/change/">View User</a>')
            # View invoices
            invoice_count = obj.user.invoices.filter(subscription=obj).count()
            if invoice_count > 0:
                links.append(f'<a href="/admin/metering/invoice/?subscription__id__exact={obj.id}">Invoices ({invoice_count})</a>')
            return format_html(' | '.join(links))
        return '-'
    quick_actions.short_description = 'Actions'
    
    def subscription_info(self, obj):
        """Display subscription information"""
        if not obj.pk:
            return 'Save subscription first'
        
        html = f'''
        <div style="padding: 10px; background: #f5f5f5; border-radius: 5px;">
            <p><strong>Plan:</strong> {obj.plan.name}</p>
            <p><strong>Price:</strong> ₹{obj.plan.price} / {obj.plan.billing_period}</p>
            <p><strong>User:</strong> <a href="/admin/core/user/{obj.user.id}/change/">{obj.user.username}</a></p>
            <p><strong>Email:</strong> {obj.user.email}</p>
        </div>
        '''
        return format_html(html)
    subscription_info.short_description = 'Subscription Information'
    
    def usage_display(self, obj):
        """Display usage information"""
        if not obj.pk:
            return 'Save subscription first'
        
        from metering.services import get_usage
        usage_items = []
        for pf in obj.plan.planfeature_set.all():
            used = get_usage(obj.user.id, pf.feature.code)
            limit_str = 'Unlimited' if pf.limit == -1 else str(pf.limit)
            remaining = pf.limit - used if pf.limit != -1 else '∞'
            
            usage_items.append(f'''
            <div style="margin-bottom: 8px; padding: 6px; background: #fff; border-left: 3px solid #17a2b8;">
                <strong>{pf.feature.name}</strong>: {used} / {limit_str} (Remaining: {remaining})
            </div>
            ''')
        
        if usage_items:
            html = '<div>' + ''.join(usage_items) + '</div>'
            return format_html(html)
        return format_html('<p style="color: #999;">No usage data</p>')
    usage_display.short_description = 'Usage'
    
    def invoice_count_display(self, obj):
        """Display invoice count"""
        if not obj.pk:
            return 'Save subscription first'
        
        count = obj.user.invoices.filter(subscription=obj).count()
        if count > 0:
            url = reverse('admin:metering_invoice_changelist') + f'?subscription__id__exact={obj.id}'
            return format_html('<a href="{}">View {} invoice(s)</a>', url, count)
        return '0 invoices'
    invoice_count_display.short_description = 'Invoices'
