"""
URL configuration for subscriptionEngine project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.views.static import serve
from core.views import ApiOverview
from django.conf import settings
from django.conf.urls.static import static
import os

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('core.urls')),
    path('api/subscriptions/', include('subscriptions.urls')),
    path('api/metering/', include('metering.urls')),
    path('api/', ApiOverview.as_view(), name='api-overview'),
    
    # Frontend routes - support both with and without /frontend/ prefix
    path('', TemplateView.as_view(template_name='frontend/index.html'), name='home'),
    path('index.html', TemplateView.as_view(template_name='frontend/index.html'), name='index'),
    path('frontend/', TemplateView.as_view(template_name='frontend/index.html'), name='frontend-home'),
    path('frontend/index.html', TemplateView.as_view(template_name='frontend/index.html'), name='frontend-index'),
    
    # Plans page
    path('plans.html', TemplateView.as_view(template_name='frontend/plans.html'), name='plans'),
    path('frontend/plans.html', TemplateView.as_view(template_name='frontend/plans.html'), name='frontend-plans'),
    
    # Invoices page
    path('invoices.html', TemplateView.as_view(template_name='frontend/invoices.html'), name='invoices'),
    path('frontend/invoices.html', TemplateView.as_view(template_name='frontend/invoices.html'), name='frontend-invoices'),
    
    # Webhooks page
    path('webhooks.html', TemplateView.as_view(template_name='frontend/webhooks.html'), name='webhooks'),
    path('frontend/webhooks.html', TemplateView.as_view(template_name='frontend/webhooks.html'), name='frontend-webhooks'),
    
    # API Testing page
    path('api-test.html', TemplateView.as_view(template_name='frontend/api-test.html'), name='api-test'),
    path('frontend/api-test.html', TemplateView.as_view(template_name='frontend/api-test.html'), name='frontend-api-test'),
    
    # Serve frontend static files (CSS, JS) - MUST be before static() to work in production
    # These paths match the relative paths in HTML (css/styles.css, js/api.js)
    path('css/<path:path>', serve, {'document_root': os.path.join(settings.BASE_DIR, 'frontend', 'css')}),
    path('js/<path:path>', serve, {'document_root': os.path.join(settings.BASE_DIR, 'frontend', 'js')}),
    path('frontend/css/<path:path>', serve, {'document_root': os.path.join(settings.BASE_DIR, 'frontend', 'css')}),
    path('frontend/js/<path:path>', serve, {'document_root': os.path.join(settings.BASE_DIR, 'frontend', 'js')}),
]

# Serve media files
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)




