from django.urls import path
from .views import (
    SubscriptionPlansView,
    InitiateSTKPushView,
    STKPushCallbackView,
    CheckSubscriptionStatusView,
    check_stk_status,
    stk_transaction_details
)
from core import views

urlpatterns = [
    path('', views.index, name='home'),
    path('plans/', SubscriptionPlansView.as_view(), name='plans'),
    path('initiate-stk/', InitiateSTKPushView.as_view(), name='initiate_stk'),
    path('check-stk-status/', check_stk_status, name='check_stk_status'),
    path('stk_transaction_details/', stk_transaction_details, name='transaction_details'),
    path('stk-callback/', STKPushCallbackView.as_view(), name='stk-callback'),
    path('check-subscription/', CheckSubscriptionStatusView.as_view(), name='check-subscription'),
]
