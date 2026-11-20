from django.db import models
from django.contrib.auth.models import User

class Plan(models.Model):
    name = models.CharField(max_length=100)
    badge_label = models.CharField(max_length=50, default="Featured Boost", blank=True)
    price_paise = models.PositiveIntegerField()      # e.g. 9900 paise = ₹99
    duration_days = models.PositiveIntegerField(default=7)
    description = models.CharField(max_length=255, blank=True)
    is_popular = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    @property
    def price_inr(self):
        return self.price_paise / 100

    class Meta:
        ordering = ['price_paise']

    def __str__(self):
        return f"{self.name} (₹{int(self.price_inr)} for {self.duration_days} days)"

class Payment(models.Model):
    STATUS = [
        ('created', 'Created'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded')
    ]
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='payments')
    ad = models.ForeignKey('ads.Ads', on_delete=models.PROTECT, related_name='payments')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    amount_paise = models.PositiveIntegerField()
    razorpay_order_id = models.CharField(max_length=80, unique=True, null=True, blank=True)
    razorpay_payment_id = models.CharField(max_length=80, null=True, blank=True)
    razorpay_signature = models.CharField(max_length=150, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='created')
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    @property
    def amount_inr(self):
        return self.amount_paise / 100

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment #{self.id} - {self.ad.title} - {self.status.upper()}"
