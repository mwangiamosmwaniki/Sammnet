from rest_framework import serializers
from .models import SubscriptionPlan, UserSubscription, STKPushTransaction

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = '__all__'

class UserSubscriptionSerializer(serializers.ModelSerializer):
    plan = SubscriptionPlanSerializer(read_only=True)
    class Meta:
        model = UserSubscription
        fields = '__all__'

class STKPushTransactionSerializer(serializers.ModelSerializer):
    plan = SubscriptionPlanSerializer(read_only=True)
    class Meta:
        model = STKPushTransaction
        fields = '__all__'
