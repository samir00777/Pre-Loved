from ads.models import Ads, Category, State, Wishlist

def footer_recent_ads(request):
    ads = Ads.objects.filter(is_active=True).order_by('-date_created')[0:3]
    wishlist_count = 0
    wishlist_ids = set()

    if request.user.is_authenticated:
        user_wishlists = Wishlist.objects.filter(user=request.user).values_list('ad_id', flat=True)
        wishlist_ids = set(user_wishlists)
        wishlist_count = len(wishlist_ids)

    return {
        'footer_recent_ads': ads,
        'nav_categories': Category.objects.filter(parent__isnull=True).prefetch_related('subcategories').order_by('id'),
        'all_categories': Category.objects.all().order_by('category_name'),
        'nav_states': State.objects.all().order_by('state_name'),
        'wishlist_count': wishlist_count,
        'user_wishlist_ids': wishlist_ids,
    }
