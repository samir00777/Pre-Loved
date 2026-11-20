from django.shortcuts import render, get_object_or_404
from django.db.models import Count, Q
from ads.models import Ads, State, City, Category, AdsImages, AdsTopBanner, AdsRightBanner, AdsBottomBanner

# Category metadata for visual styling (icons, colors, badges, and premium SVGs)
CATEGORY_META = {
    'cars': {
        'icon': 'lni-car',
        'badge': 'Vehicles',
        'color': '#2563eb',
        'bg': '#eff6ff',
        'svg': '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.5 2.8C1.4 11.1 1 11.8 1 12.6V16c0 .6.4 1 1 1h2"/><circle cx="7" cy="17" r="2"/><path d="M9 17h6"/><circle cx="17" cy="17" r="2"/></svg>'
    },
    'bikes': {
        'icon': 'lni-delivery',
        'badge': 'Two-Wheelers',
        'color': '#0d9488',
        'bg': '#f0fdfa',
        'svg': '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18.5" cy="17.5" r="3.5"/><circle cx="5.5" cy="17.5" r="3.5"/><circle cx="15" cy="5" r="1"/><path d="M12 17.5V14l-3-3 4-3 2 3h2"/></svg>'
    },
    'commercial-vehicles': {
        'icon': 'lni-van',
        'badge': 'Commercial',
        'color': '#ea580c',
        'bg': '#fff7ed',
        'svg': '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="3" width="15" height="13"/><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/></svg>'
    },
    'mobiles': {
        'icon': 'lni-mobile',
        'badge': 'Smartphones',
        'color': '#7c3aed',
        'bg': '#f5f3ff',
        'svg': '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="2" width="14" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg>'
    },
    'electronics-appliances': {
        'icon': 'lni-laptop',
        'badge': 'Electronics',
        'color': '#4f46e5',
        'bg': '#eef2ff',
        'svg': '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="2" y1="20" x2="22" y2="20"/></svg>'
    },
    'furniture-home': {
        'icon': 'lni-home',
        'badge': 'Furniture',
        'color': '#059669',
        'bg': '#ecfdf5',
        'svg': '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 9V6a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v3"/><path d="M3 16a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-5a2 2 0 0 0-4 0v2H7v-2a2 2 0 0 0-4 0z"/><path d="M5 18v2"/><path d="M19 18v2"/></svg>'
    },
    'fashion': {
        'icon': 'lni-tshirt',
        'badge': 'Fashion',
        'color': '#e11d48',
        'bg': '#fff1f2',
        'svg': '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.38 3.46 16 2a4 4 0 0 1-8 0L3.62 3.46a2 2 0 0 0-1.34 2.23l.58 3.47a1 1 0 0 0 .99.84H6v10c0 1.1.9 2 2 2h8a2 2 0 0 0 2-2V10h2.15a1 1 0 0 0 .99-.84l.58-3.47a2 2 0 0 0-1.34-2.23z"/></svg>'
    },
    'kids-baby': {
        'icon': 'lni-gift',
        'badge': 'Kids & Toys',
        'color': '#d97706',
        'bg': '#fffbeb',
        'svg': '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 12 20 22 4 22 4 12"/><rect x="2" y="7" width="20" height="5"/><line x1="12" y1="22" x2="12" y2="7"/><path d="M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7z"/><path d="M12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7z"/></svg>'
    },
    'books-sports-hobbies': {
        'icon': 'lni-book',
        'badge': 'Books & Sports',
        'color': '#0284c7',
        'bg': '#f0f9ff',
        'svg': '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>'
    },
    'tools-machinery': {
        'icon': 'lni-cog',
        'badge': 'Tools',
        'color': '#475569',
        'bg': '#f1f5f9',
        'svg': '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>'
    },
    'properties': {
        'icon': 'lni-apartment',
        'badge': 'Real Estate',
        'color': '#1e40af',
        'bg': '#eff6ff',
        'svg': '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>'
    },
    'others': {
        'icon': 'lni-package',
        'badge': 'Others',
        'color': '#6366f1',
        'bg': '#eef2ff',
        'svg': '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>'
    },
}

def home(request):
    """
    Enhanced Front Page / Homepage Dashboard:
    - 12 Newest active listings
    - Top featured ads
    - 12 Parent categories with live counts & icons
    - Popular cities with listing velocity
    - Complete search parameters (state, category, keyword)
    """
    # Fetch recent active ads (12 newest)
    recent_ads = (
        Ads.objects.filter(is_active=True)
        .select_related('category', 'category__parent', 'city', 'state', 'author__user')
        .prefetch_related('adsimages_set')
        .order_by('-id')[:12]
    )

    # Fetch featured Ads
    featured_ads = (
        Ads.objects.filter(is_featured=True, is_active=True)
        .select_related('category', 'category__parent', 'city', 'state', 'author__user')
        .prefetch_related('adsimages_set')
        .order_by('-id')[:8]
    )
    if not featured_ads.exists():
        featured_ads = recent_ads[:4]

    # Browse Ads by Category (Parent Categories with Subcategories & Counts)
    parents = Category.objects.filter(parent__isnull=True).prefetch_related('subcategories').order_by('id')
    parent_categories = []
    for p in parents:
        sub_ids = list(p.subcategories.values_list('id', flat=True))
        c_count = Ads.objects.filter(Q(category=p) | Q(category_id__in=sub_ids), is_active=True).count()
        meta = CATEGORY_META.get(p.slug, {'icon': 'lni-folder', 'badge': 'Category', 'color': '#4f46e5', 'bg': '#eef2ff', 'svg': ''})
        parent_categories.append({
            'id': p.id,
            'name': p.category_name,
            'slug': p.slug,
            'count': c_count,
            'icon': meta['icon'],
            'color': meta.get('color', '#4f46e5'),
            'bg': meta.get('bg', '#eef2ff'),
            'svg': meta.get('svg', ''),
            'badge': meta['badge'],
            'subcategories': p.subcategories.all()
        })

    # Browse Ads by State
    state_listing = State.objects.all().order_by('state_name')

    # Popular Cities
    popular_cities = (
        City.objects.annotate(ads_count=Count('ads'))
        .filter(ads_count__gt=0)
        .order_by('-ads_count')[:8]
    )

    # Fetch Ads Banner (preserved for backwards compatibility)
    sidebar_banners = AdsRightBanner.objects.all()
    top_banner = AdsTopBanner.objects.all()
    bottom_banner = AdsBottomBanner.objects.all()

    # Search options
    state_search = State.objects.values_list('state_name', flat=True).distinct().order_by("state_name")
    category_search = Category.objects.filter(parent__isnull=True).values_list('category_name', flat=True).distinct().order_by("category_name")

    total_ads_count = Ads.objects.filter(is_active=True).count()
    total_categories_count = Category.objects.filter(parent__isnull=False).count()

    context = {
        'recent_ads': recent_ads,
        'featured_ads': featured_ads,
        'parent_categories': parent_categories,
        'popular_cities': popular_cities,
        'state_search': state_search,
        'category_search': category_search,
        'category_listing': parents,
        'state_listing': state_listing,
        'sidebar_banners': sidebar_banners,
        'top_banner': top_banner,
        'bottom_banner': bottom_banner,
        'total_ads_count': total_ads_count,
        'total_categories_count': total_categories_count,
    }

    return render(request, 'pages/index.html', context)

def faq(request):
    return render(request, 'pages/faq.html')

def terms_of_service(request):
    return render(request, 'pages/terms-of-service.html')

def contact(request):
    return render(request, 'pages/contact.html')
