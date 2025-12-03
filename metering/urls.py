from django.urls import path
from .views import (
    UsageEventView, 
    UsageSummaryView,
    InvoiceListView,
    InvoiceDetailView,
    InvoiceDownloadView,
    GenerateTestInvoiceView
)

urlpatterns = [
    path('event/', UsageEventView.as_view(), name='usage-event'),
    path('summary/', UsageSummaryView.as_view(), name='usage-summary'),
    path('invoices/', InvoiceListView.as_view(), name='invoice-list'),
    path('invoices/<int:pk>/', InvoiceDetailView.as_view(), name='invoice-detail'),
    path('invoices/<int:pk>/download/', InvoiceDownloadView.as_view(), name='invoice-download'),
    path('invoices/generate-test/', GenerateTestInvoiceView.as_view(), name='generate-test-invoice'),
]
