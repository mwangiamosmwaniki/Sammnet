from django.core.management.base import BaseCommand
from core.models import STKPushTransaction
from django.utils import timezone
from datetime import timedelta

class Command(BaseCommand):
    help = 'Mark old pending STK transactions as Timed Out'

    def handle(self, *args, **kwargs):
        timeout_minutes = 3
        threshold = timezone.now() - timedelta(minutes=timeout_minutes)
        stale_transactions = STKPushTransaction.objects.filter(status='Pending', created_at__lt=threshold)

        count = stale_transactions.update(status='Timed Out')
        self.stdout.write(f"{count} transaction(s) marked as Timed Out.")
