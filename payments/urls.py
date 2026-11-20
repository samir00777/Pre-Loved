from django.urls import path
from . import views

urlpatterns = [
    path('promote/<int:ad_id>/', views.promote_ad_view, name='payments-promote'),
    path('order/create/<int:ad_id>/<int:plan_id>/', views.create_order, name='payments-create-order'),
    path('verify/', views.verify_payment, name='payments-verify'),
    path('webhook/', views.razorpay_webhook, name='payments-webhook'),
]
