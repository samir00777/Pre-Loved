from django.db import models
from ckeditor.fields import RichTextField
from django.utils.text import slugify
from django.urls import reverse
# Default User model
from django.contrib.auth.models import User

from embed_video.fields import EmbedVideoField

# Create your models here.

# Author Model
class Author(models.Model):
    user = models.OneToOneField(User, on_delete = models.CASCADE)
    profile_pic = models.ImageField(default="default-profile-pic.png", upload_to='uploads/profile-pictures', null=True)

    def __str__(self):
        return self.user.username

# Ads Model
class Ads(models.Model):
    
    CONDITION = (
        ('Like New', 'Like New'),
        ('Good', 'Good'),
        ('Fair', 'Fair'),
        ('Needs Repair', 'Needs Repair'),
    )

    author = models.ForeignKey(Author, on_delete=models.CASCADE, null=True)
    title = models.CharField(max_length=200)
    description = RichTextField()
    price = models.DecimalField(max_digits=14, decimal_places=2)
    date_created = models.DateTimeField(auto_now_add=True)
    state = models.ForeignKey('State', on_delete=models.CASCADE, null=True, blank=True)
    city = models.ForeignKey('City', on_delete=models.CASCADE, null=True, blank=True)
    area = models.CharField(max_length=200, blank=True, null=True)
    seller_name = models.CharField(max_length=150, blank=True, null=True)
    category = models.ForeignKey('Category', on_delete=models.CASCADE, null=True) 
    condition = models.CharField(max_length=100, choices=CONDITION)
    brand = models.CharField(max_length=200, blank=True, null=True)
    phone = models.CharField(max_length=50)
    is_phone_verified = models.BooleanField(default=True)
    video = EmbedVideoField(null=True, blank=True) 
    is_featured = models.BooleanField(default=False)
    featured_until = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_sold = models.BooleanField(default=False)

    @property
    def is_sold_out(self):
        return self.is_sold or not self.is_active

    # Common Optional Fields
    is_negotiable = models.BooleanField(default=False)
    purchase_year = models.CharField(max_length=50, blank=True, null=True)
    reason_for_selling = models.CharField(max_length=300, blank=True, null=True)
    bill_or_warranty = models.CharField(max_length=150, blank=True, null=True)
    exchange_accepted = models.BooleanField(default=False)
    preferred_contact = models.CharField(max_length=50, default='Any', blank=True, null=True)
    preferred_contact_time = models.CharField(max_length=100, blank=True, null=True)
    delivery_available = models.CharField(max_length=50, default='Pickup Only', blank=True, null=True)
    seller_type = models.CharField(max_length=50, default='Owner', blank=True, null=True)
    test_ride_available = models.BooleanField(default=False)
    registration_number = models.CharField(max_length=50, blank=True, null=True)
    is_rc_verified = models.BooleanField(default=False)

    # Category-Specific Extra Fields (Dynamic JSON dictionary)
    extra_details = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "Classified Ads"

    def __str__(self):
        return self.title

# State Model
class State(models.Model):
    state_name = models.CharField(max_length=100)
    slug = models.SlugField(blank=True, null=True)

    # overriding save method to add slug field from state name if not provided
    def save(self, *args, **kwargs):
        if not self.slug and self.state_name:
            self.slug = slugify(self.state_name)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name_plural = "States"

    def __str__(self):
        return self.state_name

# City Model
class City(models.Model):
    city_name = models.CharField(max_length=100)
    slug = models.SlugField(blank=True, null=True)

    # overriding save method to add slug field from city name if not provided
    def save(self, *args, **kwargs):
        if not self.slug and self.city_name:
            self.slug = slugify(self.city_name)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name_plural = "Cities"

    def __str__(self):
        return self.city_name

# Category Model
class Category(models.Model):
    category_name = models.CharField(max_length=150)
    category_image = models.ImageField(upload_to='uploads/category', blank=True, null=True)
    slug = models.SlugField(max_length=150, blank=True, null=True, unique=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subcategories')

    # overriding save method to add slug field from category name if not provided
    def save(self, *args, **kwargs):
        if not self.slug and self.category_name:
            base_slug = slugify(self.category_name)
            if self.parent:
                base_slug = f"{slugify(self.parent.category_name)}-{base_slug}"
            slug = base_slug[:140]
            counter = 1
            while Category.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug[:130]}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        if self.parent:
            return f"{self.parent.category_name} > {self.category_name}"
        return self.category_name

# Image Model
class AdsImages(models.Model):
    ads = models.ForeignKey(Ads, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='uploads/%Y/%m/%d', default=None)

    def __str__(self):
        return self.ads.title

    class Meta:
        verbose_name_plural = 'Classified Ads Images'

# Top Banner Model
class AdsTopBanner(models.Model):
    title = models.CharField(max_length=200, default="Place Your Ad", blank=True)
    image = models.ImageField(upload_to='banners/%Y/%m/%d', default=None)

    def __str__(self):
        return self.title

# Right Banner Model
class AdsRightBanner(models.Model):
    title = models.CharField(max_length=200, default="Place Your Ad", blank=True)
    image = models.ImageField(upload_to='banners/%Y/%m/%d', default=None)

    def __str__(self):
        return self.title

# Bottom Banner Model
class AdsBottomBanner(models.Model):
    title = models.CharField(max_length=200, default="Place Your Ad", blank=True)
    image = models.ImageField(upload_to='banners/%Y/%m/%d', default=None)

    def __str__(self):
        return self.title

# User Wishlist Model
class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlist_items')
    ad = models.ForeignKey(Ads, on_delete=models.CASCADE, related_name='wishlisted_by')
    date_added = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Wishlist Item"
        verbose_name_plural = "Wishlist Items"
        unique_together = ('user', 'ad')
        ordering = ['-date_added']

    def __str__(self):
        return f"{self.user.username} - {self.ad.title}"


# Call Request / Callback Inquiry Model
class CallRequest(models.Model):
    TIME_CHOICES = (
        ('Anytime', 'Anytime (Best available)'),
        ('Morning', 'Morning (9:00 AM - 12:00 PM)'),
        ('Afternoon', 'Afternoon (12:00 PM - 5:00 PM)'),
        ('Evening', 'Evening (5:00 PM - 9:00 PM)'),
    )

    ad = models.ForeignKey(Ads, on_delete=models.CASCADE, related_name='call_requests')
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_call_requests')
    buyer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_call_requests')
    buyer_name = models.CharField(max_length=150)
    buyer_phone = models.CharField(max_length=20)
    message = models.TextField(blank=True, null=True)
    preferred_time = models.CharField(max_length=50, choices=TIME_CHOICES, default='Anytime')
    is_contacted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Call Request"
        verbose_name_plural = "Call Requests"
        ordering = ['-created_at']

    def __str__(self):
        return f"Call Request: {self.buyer_name} ({self.buyer_phone}) for {self.ad.title}"


