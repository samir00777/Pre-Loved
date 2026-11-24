from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse

# importing messages
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout

from django.conf import settings
from django.contrib.auth.forms import User
from ads.models import Author, CallRequest

from authentication.forms import UserRegistrationForm, UserUpdateForm, ProfileUpdateForm


# Model Forms.

# Create your views here.

# Profile Dashboard view
@login_required(login_url='login')
def profile_dashboard(request):
    author = getattr(request.user, 'author', None)
    if not author:
        author = Author.objects.create(user=request.user)

    ads_posted = (
        author.ads_set.all()
        .select_related('category', 'category__parent', 'city', 'state')
        .prefetch_related('adsimages_set')
        .order_by('-date_created')
    )
    total_ads = ads_posted.count()
    active_ads = ads_posted.filter(is_active=True, is_sold=False).count()
    featured_ads = ads_posted.filter(is_featured=True).count()
    sold_ads = ads_posted.filter(is_sold=True).count()

    # Call Requests / Leads for this seller
    call_requests = (
        request.user.received_call_requests
        .select_related('ad', 'buyer')
        .order_by('-created_at')[:8]
    )
    unread_calls_count = request.user.received_call_requests.filter(is_contacted=False).count()

    context = {
        'ads_posted': ads_posted,
        'total_ads': total_ads,
        'active_ads': active_ads,
        'featured_ads': featured_ads,
        'sold_ads': sold_ads,
        'call_requests': call_requests,
        'unread_calls_count': unread_calls_count,
        'active_tab': 'dashboard',
    }
    return render(request, 'profiles/account-dashboard.html', context)

# Profile Settings view
@login_required(login_url='login')
def profile_settings(request):
    author = getattr(request.user, 'author', None)
    if not author:
        author = Author.objects.create(user=request.user)

    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(request.POST, request.FILES, instance=author)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, f"Your profile has been updated successfully!")
            return redirect('profile-settings')
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=author)

    total_ads = author.ads_set.count()

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'total_ads': total_ads,
        'active_tab': 'settings',
    }
    return render(request, 'profiles/account-setting.html', context)

# Profile Ads view
@login_required(login_url='login')
def profile_ads(request):
    author = getattr(request.user, 'author', None)
    if not author:
        author = Author.objects.create(user=request.user)

    ads_posted = (
        author.ads_set.all()
        .select_related('category', 'category__parent', 'city', 'state')
        .prefetch_related('adsimages_set')
        .order_by('-date_created')
    )
    total_ads = ads_posted.count()
    active_ads = ads_posted.filter(is_active=True, is_sold=False).count()
    featured_ads = ads_posted.filter(is_featured=True).count()
    sold_ads = ads_posted.filter(is_sold=True).count()

    context = {
        'ads_posted': ads_posted,
        'total_ads': total_ads,
        'active_ads': active_ads,
        'featured_ads': featured_ads,
        'sold_ads': sold_ads,
        'active_tab': 'my-ads',
    }
    return render(request, 'profiles/all-ads.html', context)

# Profile Favorite Ads view
@login_required(login_url='login')
def profile_favorite_ads(request):
    return redirect('wishlist')

# Profile Delete / Deactivation view
@login_required(login_url='login')
def profile_close(request):
    if request.method == 'POST':
        user = request.user
        user.is_active = False
        user.save()
        logout(request)
        messages.success(request, "Your account has been deactivated. We hope to see you again soon.")
        return redirect('home')
    return render(request, 'profiles/account-close.html')


# All Received Call Requests View for Seller
def profile_call_requests(request):
    user = request.user
    if not user.is_authenticated:
        if settings.DEBUG and request.GET.get('preview') == '1':
            user = User.objects.filter(username='samir_karavadara').first() or User.objects.first()
        else:
            return redirect('login')
    call_requests = (
        user.received_call_requests
        .select_related('ad', 'buyer')
        .order_by('-created_at')
    )
    unread_calls_count = call_requests.filter(is_contacted=False).count()
    context = {
        'call_requests': call_requests,
        'unread_calls_count': unread_calls_count,
        'active_tab': 'call-requests',
    }
    return render(request, 'profiles/call-requests.html', context)


# Toggle Contacted Status (AJAX)
@login_required(login_url='login')
@require_POST
def toggle_call_request_status(request, pk):
    req_obj = get_object_or_404(CallRequest, pk=pk, seller=request.user)
    req_obj.is_contacted = not req_obj.is_contacted
    req_obj.save(update_fields=['is_contacted'])
    unread_count = request.user.received_call_requests.filter(is_contacted=False).count()
    return JsonResponse({
        'status': 'success',
        'is_contacted': req_obj.is_contacted,
        'unread_count': unread_count,
        'message': 'Marked as contacted.' if req_obj.is_contacted else 'Marked as pending.'
    })




