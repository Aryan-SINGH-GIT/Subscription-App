from django.urls import path
from .views import PlanListView, SubscriptionView, ChangePlanView, RenewSubscriptionView

urlpatterns = [
    path('plans/', PlanListView.as_view(), name='plan-list'),
    path('subscribe/', SubscriptionView.as_view(), name='subscription'),
    path('change-plan/', ChangePlanView.as_view(), name='subscription-change-plan'),
    path('renew/', RenewSubscriptionView.as_view(), name='subscription-renew'),
]
