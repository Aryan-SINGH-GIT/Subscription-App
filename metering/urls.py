from django.urls import path
from .views import UsageEventView, UsageSummaryView

urlpatterns = [
    path('event/', UsageEventView.as_view(), name='usage-event'),
    path('summary/', UsageSummaryView.as_view(), name='usage-summary'),
]
