from django.contrib import admin
from .models import SubscriptionPlan, UserSubscription, STKPushTransaction

admin.site.register(SubscriptionPlan)
admin.site.register(UserSubscription)
admin.site.register(STKPushTransaction)
