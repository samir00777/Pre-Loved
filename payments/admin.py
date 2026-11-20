from django.contrib import admin
from .models import Plan, Payment

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'badge_label', 'price_inr', 'duration_days', 'is_popular', 'is_active')
    list_editable = ('is_popular', 'is_active')
    search_fields = ('name', 'badge_label')

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'ad', 'plan', 'amount_inr', 'status', 'razorpay_order_id', 'created_at', 'paid_at')
    list_filter = ('status', 'created_at', 'plan')
    search_fields = ('user__username', 'ad__title', 'razorpay_order_id', 'razorpay_payment_id')
    readonly_fields = ('created_at', 'paid_at')
