from django.db import models
from django.utils import timezone
from datetime import timedelta

class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100, null=True, blank=True)
    validity = models.CharField(max_length=20)  # e.g., '1 Hour', '1 Day'
    amount = models.DecimalField(max_digits=10, decimal_places=2)  # Amount in your currency

    def __str__(self):
        return f"{self.validity} - {self.amount}"


class UserSubscription(models.Model):
    phone_number = models.CharField(max_length=15)  # Stored in international format, e.g., 2547XXXXXXXX
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField()

    def save(self, *args, **kwargs):
        if not self.end_time:
            # Calculate end_time based on plan validity
            if "Hour" in self.plan.validity:
                hours = int(self.plan.validity.split()[0])
                self.end_time = self.start_time + timedelta(hours=hours)
            elif "Day" in self.plan.validity or "Days" in self.plan.validity:
                days = int(self.plan.validity.split()[0])
                self.end_time = self.start_time + timedelta(days=days)
            elif "Week" in self.plan.validity or "Weeks" in self.plan.validity:
                weeks = int(self.plan.validity.split()[0])
                self.end_time = self.start_time + timedelta(weeks=weeks)
            else:
                # Default 1 hour if unknown format
                self.end_time = self.start_time + timedelta(hours=1)
        super().save(*args, **kwargs)

    def is_active(self):
        return timezone.now() < self.end_time

    def __str__(self):
        return f"{self.phone_number} - {self.plan.validity} active till {self.end_time}"


class STKPushTransaction(models.Model):
    phone_number = models.CharField(max_length=15)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    checkout_request_id = models.CharField(unique=True, max_length=100, blank=True, null=True)  # ID from MPesa (simulated)
    status = models.CharField(max_length=20, null=True, blank=True)  # Pending, Success, Cancelled, Timeout
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.phone_number} - {self.plan.validity} - {self.status}"
