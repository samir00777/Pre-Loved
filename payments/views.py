import hmac
import hashlib
import json
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.urls import reverse

from ads.models import Ads
from .models import Plan, Payment

def _get_razorpay_client():
    key_id = getattr(settings, 'RAZORPAY_KEY_ID', None)
    key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', None)
    if key_id and key_secret and not key_id.startswith('rzp_placeholder') and not key_id.startswith('rzp_test_placeholder'):
        try:
            import razorpay
            return razorpay.Client(auth=(key_id, key_secret))
        except Exception:
            return None
    return None

def _sign(secret, msg):
    if not secret:
        secret = "preloved_dev_secret"
    return hmac.new(secret.encode('utf-8'), msg, hashlib.sha256).hexdigest()

def mark_paid(order_id, payment_id, signature=""):
    with transaction.atomic():
        pay = Payment.objects.select_for_update().get(razorpay_order_id=order_id)
        if pay.status == 'paid':
            return pay
        pay.status = 'paid'
        pay.razorpay_payment_id = payment_id
        pay.razorpay_signature = signature
        pay.paid_at = timezone.now()
        pay.save(update_fields=['status', 'razorpay_payment_id', 'razorpay_signature', 'paid_at'])

        ad = pay.ad
        current_time = timezone.now()
        start = max(ad.featured_until or current_time, current_time)
        ad.is_featured = True
        ad.featured_until = start + timedelta(days=pay.plan.duration_days)
        ad.save(update_fields=['is_featured', 'featured_until'])
    return pay

# Promote Ad Plan Selection Page
@login_required(login_url='login')
def promote_ad_view(request, ad_id):
    ad = get_object_or_404(Ads, pk=ad_id)

    # Permission check: seller or admin
    if ad.author and ad.author.user != request.user and not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Permission denied: You can only promote your own classified listings.")
        return redirect('dashboard')

    plans = Plan.objects.filter(is_active=True).order_by('price_paise')
    if not plans.exists():
        # Seed standard default plans if empty
        Plan.objects.create(name="Fast 7-Day Boost", badge_label="Weekly Boost", price_paise=9900, duration_days=7, description="High search priority and featured badge for 7 days.", is_popular=False)
        Plan.objects.create(name="Premium 30-Day Highlight", badge_label="Most Popular", price_paise=24900, duration_days=30, description="Top homepage placement, gold featured badge, and 5x buyer views.", is_popular=True)
        Plan.objects.create(name="Mega 90-Day VIP Feature", badge_label="Best Value", price_paise=59900, duration_days=90, description="Quarterly featured promotion with prime category placement.", is_popular=False)
        plans = Plan.objects.filter(is_active=True).order_by('price_paise')

    razorpay_key = getattr(settings, 'RAZORPAY_KEY_ID', 'rzp_test_placeholder')

    context = {
        'ad': ad,
        'plans': plans,
        'razorpay_key': razorpay_key,
    }
    return render(request, 'payments/promote.html', context)

# Create Order Endpoint (AJAX)
@login_required(login_url='login')
@require_POST
def create_order(request, ad_id, plan_id):
    ad = get_object_or_404(Ads, pk=ad_id)
    if ad.author and ad.author.user != request.user and not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)

    plan = get_object_or_404(Plan, pk=plan_id, is_active=True)

    pay = Payment.objects.create(
        user=request.user,
        ad=ad,
        plan=plan,
        amount_paise=plan.price_paise,
        status='created'
    )

    client = _get_razorpay_client()
    if client:
        try:
            order = client.order.create({
                "amount": plan.price_paise,
                "currency": "INR",
                "receipt": f"PL_{pay.id}",
                "notes": {
                    "ad_id": str(ad.id),
                    "plan_name": plan.name,
                    "user_id": str(request.user.id)
                }
            })
            pay.razorpay_order_id = order["id"]
            pay.save(update_fields=['razorpay_order_id'])
            return JsonResponse({
                "status": "success",
                "key": getattr(settings, 'RAZORPAY_KEY_ID', ''),
                "order_id": order["id"],
                "amount": plan.price_paise,
                "currency": "INR",
                "ad_title": ad.title,
                "plan_name": plan.name
            })
        except Exception as e:
            # Fallback to simulated test order
            pass

    # Simulated Sandbox Test Order Mode
    simulated_order_id = f"order_sim_{uuid.uuid4().hex[:14]}"
    pay.razorpay_order_id = simulated_order_id
    pay.save(update_fields=['razorpay_order_id'])

    return JsonResponse({
        "status": "success",
        "is_sandbox": True,
        "key": getattr(settings, 'RAZORPAY_KEY_ID', 'rzp_test_dev'),
        "order_id": simulated_order_id,
        "amount": plan.price_paise,
        "currency": "INR",
        "ad_title": ad.title,
        "plan_name": plan.name
    })

# Verify Payment Endpoint (AJAX)
@login_required(login_url='login')
@require_POST
def verify_payment(request):
    oid = request.POST.get('razorpay_order_id', '').strip()
    pid = request.POST.get('razorpay_payment_id', '').strip()
    sig = request.POST.get('razorpay_signature', '').strip()

    if not oid:
        return JsonResponse({"status": "error", "message": "Missing order reference."}, status=400)

    pay = get_object_or_404(Payment, razorpay_order_id=oid, user=request.user)

    secret = getattr(settings, 'RAZORPAY_KEY_SECRET', 'placeholder_secret')
    client = _get_razorpay_client()

    # If live/test signature provided
    if not oid.startswith('order_sim_') and client and sig:
        expected = _sign(secret, f"{oid}|{pid}".encode('utf-8'))
        if not hmac.compare_digest(expected, sig):
            pay.status = 'failed'
            pay.save(update_fields=['status'])
            return JsonResponse({"status": "error", "message": "Signature verification failed."}, status=400)
    else:
        # In sandbox test mode, generate dummy payment id if empty
        if not pid:
            pid = f"pay_sim_{uuid.uuid4().hex[:14]}"

    mark_paid(oid, pid, sig)

    return JsonResponse({
        "status": "success",
        "message": f"Listing '{pay.ad.title}' has been successfully upgraded to Featured for {pay.plan.duration_days} days!",
        "redirect_url": reverse('ads-detail', kwargs={'pk': pay.ad.id})
    })

# Razorpay Webhook Endpoint
@csrf_exempt
@require_POST
def razorpay_webhook(request):
    sig = request.headers.get('X-Razorpay-Signature', '')
    webhook_secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', '')

    if webhook_secret and not hmac.compare_digest(_sign(webhook_secret, request.body), sig):
        return HttpResponse("Signature mismatch", status=400)

    try:
        event = json.loads(request.body.decode('utf-8'))
    except Exception:
        return HttpResponse("Invalid JSON", status=400)

    event_type = event.get('event')
    if event_type in ('payment.captured', 'order.paid'):
        payload = event.get('payload', {}).get('payment', {}).get('entity', {})
        order_id = payload.get('order_id')
        payment_id = payload.get('id')
        if order_id and payment_id:
            try:
                mark_paid(order_id, payment_id)
            except Payment.DoesNotExist:
                pass

    return HttpResponse("Webhook processed", status=200)
