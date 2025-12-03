from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.core.files.base import ContentFile
from .models import MeterEvent, Invoice


def regenerate_invoice_pdfs(modeladmin, request, queryset):
    """Regenerate PDFs for selected invoices"""
    from metering.invoice_generator import generate_invoice_pdf
    
    count = 0
    for invoice in queryset:
        try:
            pdf_content = generate_invoice_pdf(invoice)
            invoice.pdf_file.save(
                f'{invoice.invoice_number}.pdf',
                ContentFile(pdf_content),
                save=True
            )
            count += 1
        except Exception as e:
            modeladmin.message_user(request, f'Error generating PDF for {invoice.invoice_number}: {e}', level='error')
    
    modeladmin.message_user(request, f'Successfully regenerated {count} PDF(s)')
regenerate_invoice_pdfs.short_description = 'Regenerate PDFs for selected invoices'


@admin.register(MeterEvent)
class MeterEventAdmin(admin.ModelAdmin):
    """Admin for MeterEvent model"""
    list_display = ('user', 'feature', 'timestamp', 'event_id_short', 'metadata_preview')
    list_filter = ('feature', 'timestamp', 'user')
    search_fields = ('user__username', 'user__email', 'feature__code', 'feature__name', 'event_id')
    readonly_fields = ('user', 'feature', 'timestamp', 'event_id', 'metadata')
    date_hierarchy = 'timestamp'
    ordering = ('-timestamp',)
    
    fieldsets = (
        ('Event Information', {
            'fields': ('user', 'feature', 'timestamp', 'event_id')
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
    )
    
    def event_id_short(self, obj):
        """Show shortened event ID"""
        if len(obj.event_id) > 20:
            return obj.event_id[:20] + '...'
        return obj.event_id
    event_id_short.short_description = 'Event ID'
    
    def metadata_preview(self, obj):
        """Show metadata preview"""
        if obj.metadata:
            import json
            preview = json.dumps(obj.metadata)[:50]
            if len(json.dumps(obj.metadata)) > 50:
                preview += '...'
            return preview
        return '-'
    metadata_preview.short_description = 'Metadata'


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    """Admin for Invoice model with detailed information"""
    list_display = ('invoice_number', 'user', 'plan_name', 'invoice_date', 'total_display', 'status_badge', 'period_info', 'pdf_link')
    list_filter = ('status', 'invoice_date', 'subscription__plan')
    search_fields = ('invoice_number', 'user__username', 'user__email', 'subscription__plan__name')
    readonly_fields = ('invoice_info', 'items_display', 'pdf_download_link')
    date_hierarchy = 'invoice_date'
    ordering = ('-invoice_date', '-created_at')
    
    fieldsets = (
        ('Invoice Details', {
            'fields': ('user', 'subscription', 'invoice_number', 'invoice_date', 'status')
        }),
        ('Billing Period', {
            'fields': ('period_start', 'period_end')
        }),
        ('Amounts', {
            'fields': ('subtotal', 'tax', 'total')
        }),
        ('Items', {
            'fields': ('items_display',),
            'classes': ('collapse',)
        }),
        ('PDF', {
            'fields': ('pdf_file', 'pdf_download_link'),
        }),
        ('Information', {
            'fields': ('invoice_info',),
            'classes': ('collapse',)
        }),
    )
    
    def plan_name(self, obj):
        """Display plan name"""
        if obj.subscription:
            return obj.subscription.plan.name
        return 'N/A'
    plan_name.short_description = 'Plan'
    
    def total_display(self, obj):
        """Display total with currency"""
        return format_html('<strong>₹{}</strong>', obj.total)
    total_display.short_description = 'Total'
    
    def status_badge(self, obj):
        """Display status with color coding"""
        colors = {
            'draft': '#6c757d',
            'finalized': '#17a2b8',
            'paid': '#28a745',
            'void': '#dc3545'
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 8px; border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.status.upper()
        )
    status_badge.short_description = 'Status'
    
    def period_info(self, obj):
        """Display billing period"""
        return f'{obj.period_start} to {obj.period_end}'
    period_info.short_description = 'Period'
    
    def pdf_link(self, obj):
        """Display PDF download link"""
        if obj.pdf_file:
            # Use the API endpoint for downloading
            url = f'/api/metering/invoices/{obj.pk}/download/'
            return format_html('<a href="{}" target="_blank">Download PDF</a>', url)
        return format_html('<span style="color: #999;">No PDF</span>')
    pdf_link.short_description = 'PDF'
    
    def invoice_info(self, obj):
        """Display invoice information"""
        if not obj.pk:
            return 'Save invoice first'
        
        html = f'''
        <div style="padding: 10px; background: #f5f5f5; border-radius: 5px;">
            <p><strong>User:</strong> <a href="/admin/core/user/{obj.user.id}/change/">{obj.user.username}</a> ({obj.user.email})</p>
            {f'<p><strong>Plan:</strong> {obj.subscription.plan.name}</p>' if obj.subscription else ''}
            <p><strong>Created:</strong> {obj.created_at.strftime("%Y-%m-%d %H:%M")}</p>
            <p><strong>Updated:</strong> {obj.updated_at.strftime("%Y-%m-%d %H:%M")}</p>
        </div>
        '''
        return format_html(html)
    invoice_info.short_description = 'Invoice Information'
    
    def items_display(self, obj):
        """Display invoice items in a readable format"""
        if not obj.items:
            return format_html('<p style="color: #999;">No items</p>')
        
        import json
        items_html = '<table style="width: 100%; border-collapse: collapse;">'
        items_html += '<tr style="background: #f0f0f0;"><th style="padding: 8px; text-align: left;">Feature</th><th style="padding: 8px; text-align: left;">Used</th><th style="padding: 8px; text-align: left;">Limit</th><th style="padding: 8px; text-align: left;">Price</th></tr>'
        
        for item in obj.items:
            feature = item.get('feature', 'N/A')
            used = item.get('used', 0)
            limit = item.get('limit', 'N/A')
            price = item.get('price', '-')
            is_overage = item.get('is_overage', False)
            
            row_style = 'background: #fff3cd;' if is_overage else ''
            items_html += f'<tr style="{row_style}"><td style="padding: 8px;">{feature}</td><td style="padding: 8px;">{used}</td><td style="padding: 8px;">{limit}</td><td style="padding: 8px;">{price if price != "-" else "-"}</td></tr>'
        
        items_html += '</table>'
        return format_html(items_html)
    items_display.short_description = 'Invoice Items'
    
    def pdf_download_link(self, obj):
        """Display PDF download link in detail view"""
        if obj.pdf_file:
            # Use the API endpoint for downloading
            url = f'/api/metering/invoices/{obj.pk}/download/'
            return format_html('<a href="{}" class="button" target="_blank">Download PDF</a>', url)
        return format_html('<span style="color: #999;">PDF not generated yet</span>')
    pdf_download_link.short_description = 'PDF Download'
