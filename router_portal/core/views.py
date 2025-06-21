from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import SubscriptionPlan, UserSubscription, STKPushTransaction
from .serializers import SubscriptionPlanSerializer
from django.utils import timezone
from datetime import timedelta
import uuid
import re
import base64
import requests
from django.conf import settings
from requests.auth import HTTPBasicAuth
from datetime import datetime
from django.shortcuts import render
from rest_framework.decorators import api_view


# Helper function to convert phone number to international format (Kenya: 2547XXXXXXXX)
def convert_phone_to_international(phone):
    phone = phone.strip()
    if phone.startswith("07"):
        return "254" + phone[1:]
    elif phone.startswith("01"):
        return "254" + phone[1:]
    elif phone.startswith("+254"):
        return phone[1:]
    elif phone.startswith("254"):
        return phone
    else:
        return None

# Render homepage with subscription plans
def index(request):
    plans = SubscriptionPlan.objects.all()
    return render(request, 'core/router_portal.html', {'plans': plans})

class SubscriptionPlansView(APIView):
    def get(self, request):
        plans = SubscriptionPlan.objects.all()
        serializer = SubscriptionPlanSerializer(plans, many=True)
        return Response(serializer.data)

class InitiateSTKPushView(APIView):
    def post(self, request):
        phone = request.data.get("phone_number")
        plan_id = request.data.get("plan_id")

        if not phone or not re.match(r'^(07|01)\d{8}$', phone):
            return Response({"error": "Invalid phone number format. Must start with 07 or 01 and be 10 digits."},
                            status=status.HTTP_400_BAD_REQUEST)

        international_phone = convert_phone_to_international(phone)
        if not international_phone:
            return Response({"error": "Could not convert phone number to international format."},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            plan = SubscriptionPlan.objects.get(id=plan_id)
        except SubscriptionPlan.DoesNotExist:
            return Response({"error": "Invalid plan selected."}, status=status.HTTP_400_BAD_REQUEST)

        # Step 1: Get access token
        token_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
        consumer_key = settings.MPESA_CONSUMER_KEY
        consumer_secret = settings.MPESA_CONSUMER_SECRET
        auth_response = requests.get(token_url, auth=HTTPBasicAuth(consumer_key, consumer_secret))

        if auth_response.status_code != 200:
            return Response({"error": "Failed to authenticate with M-Pesa API"}, status=500)

        access_token = auth_response.json().get("access_token")

        # Step 2: Prepare STK Push request
        stk_push_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password = base64.b64encode((settings.MPESA_EXPRESS_SHORTCODE + settings.MPESA_PASSKEY + timestamp).encode()).decode()

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "BusinessShortCode": settings.MPESA_EXPRESS_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(plan.amount),
            "PartyA": international_phone,
            "PartyB": settings.MPESA_EXPRESS_SHORTCODE,
            "PhoneNumber": international_phone,
            "CallBackURL": settings.MPESA_CALLBACK_URL,
            "AccountReference": "SAMNET",
            "TransactionDesc": f"Payment for {plan.name}"
        }

        response = requests.post(stk_push_url, json=payload, headers=headers)
        resp_data = response.json()

        if response.status_code != 200 or resp_data.get("ResponseCode") != "0":
            return Response({"error": "STK push failed", "details": resp_data}, status=500)

        checkout_request_id = resp_data.get("CheckoutRequestID")

        # Save transaction to DB
        transaction = STKPushTransaction.objects.create(
            phone_number=international_phone,
            plan=plan,
            amount=plan.amount,
            checkout_request_id=checkout_request_id,
            status='Pending'
        )

        return Response({
            "message": "STK Push sent to phone",
            "checkout_request_id": checkout_request_id,
            "status": "sending stk push"
        })

class STKPushCallbackView(APIView):
    """
    Endpoint to receive M-Pesa STK push callback (from M-Pesa servers via your ngrok)
    """

    def post(self, request):
        data = request.data
        # Extract stkCallback from nested structure
        stk_callback = data.get("Body", {}).get("stkCallback", {})
        checkout_request_id = stk_callback.get("CheckoutRequestID")
        result_code = stk_callback.get("ResultCode")
        result_desc = stk_callback.get("ResultDesc", "")

        if not checkout_request_id or result_code is None:
            return Response({"error": "Missing required callback parameters"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            transaction = STKPushTransaction.objects.get(checkout_request_id=checkout_request_id)
        except STKPushTransaction.DoesNotExist:
            return Response({"error": "Transaction not found"}, status=status.HTTP_404_NOT_FOUND)

        if result_code == 0:
            transaction.status = "Success"
            transaction.save()

            # Create or extend subscription logic here (like in your current code)
            subscription = UserSubscription.objects.filter(phone_number=transaction.phone_number, plan=transaction.plan).first()
            if subscription and subscription.is_active():
                if "Hour" in subscription.plan.validity:
                    hours = int(subscription.plan.validity.split()[0])
                    subscription.end_time += timedelta(hours=hours)
                elif "Day" in subscription.plan.validity or "Days" in subscription.plan.validity:
                    days = int(subscription.plan.validity.split()[0])
                    subscription.end_time += timedelta(days=days)
                elif "Week" in subscription.plan.validity or "Weeks" in subscription.plan.validity:
                    weeks = int(subscription.plan.validity.split()[0])
                    subscription.end_time += timedelta(weeks=weeks)
                subscription.save()
            else:
                UserSubscription.objects.create(
                    phone_number=transaction.phone_number,
                    plan=transaction.plan,
                    start_time=timezone.now(),
                    end_time=None  # handled in model save
                )

            return Response({"ResultCode": 0, "ResultDesc": "Callback received successfully"})

        elif result_code == 1032:
                transaction.status = "Cancelled"
                transaction.save()
                return Response({
                    "ResultCode": 0,
                    "ResultDesc": "User cancelled the transaction",
                    "CheckoutRequestID": checkout_request_id,
                    "SavedStatus": transaction.status
                })



        else:
            # Other failure codes
            transaction.status = f"Failed: {result_desc}"
            transaction.save()
            return Response({"ResultCode": 0, "ResultDesc": "Callback received, failure recorded"})

class CheckSubscriptionStatusView(APIView):
    def get(self, request):
        phone = request.query_params.get("phone_number")
        if not phone:
            return Response({"error": "phone_number parameter required"}, status=status.HTTP_400_BAD_REQUEST)

        international_phone = convert_phone_to_international(phone)
        if not international_phone:
            return Response({"error": "Invalid phone number format"}, status=status.HTTP_400_BAD_REQUEST)

        # Check if subscription is active
        active_subscriptions = UserSubscription.objects.filter(phone_number=international_phone)
        for sub in active_subscriptions:
            if sub.is_active():
                return Response({
                    "status": "connected",
                    "plan": sub.plan.validity,
                    "expires": sub.end_time
                })
        return Response({"status": "not connected"})

@api_view(['GET'])
def check_stk_status(request):
    checkout_request_id = request.query_params.get('checkout_request_id')
    if not checkout_request_id:
        return Response({"error": "checkout_request_id is required"}, status=400)
    try:
        transaction = STKPushTransaction.objects.get(checkout_request_id=checkout_request_id)
    except STKPushTransaction.DoesNotExist:
        return Response({"error": "Transaction not found"}, status=404)

    return Response({
        "status": transaction.status
    })

@api_view(['GET'])
def stk_transaction_details(request):
    checkout_request_id = request.query_params.get('checkout_request_id')
    if not checkout_request_id:
        return Response({"error": "checkout_request_id is required"}, status=400)

    try:
        transaction = STKPushTransaction.objects.get(checkout_request_id=checkout_request_id)
    except STKPushTransaction.DoesNotExist:
        return Response({"error": "Transaction not found"}, status=404)

    status_map = {
        'Success': 'success',
        'Cancelled': 'cancelled',
        'Timeout': 'timeout',
    }

    status = status_map.get(transaction.status, transaction.status.lower())

    if status != 'success':
        return Response({"status": status})

    return Response({
        "status": status,
        "amount": transaction.amount,
        "plan": transaction.plan.name,
        "timestamp": transaction.created_at.isoformat() if transaction.created_at else None,
    })


