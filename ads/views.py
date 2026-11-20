import os
import re
import json
import decimal
import bleach
from PIL import Image
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, Http404
from django.urls import reverse
from .models import *
from django.db.models import Count, Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
# Model Forms.
from .forms import PostAdsForm
from django.contrib.auth.forms import User
from django.contrib.auth.models import User

from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
import datetime

from django.conf import settings
from django.core.mail import send_mail

# importing messages
from django.contrib import messages

from ads.models import Author

# Allowed HTML tags and attributes for sanitization (Stored XSS prevention)
ALLOWED_HTML_TAGS = [
    'p', 'br', 'b', 'strong', 'i', 'em', 'u', 's', 'strike',
    'ul', 'ol', 'li', 'span', 'div', 'blockquote', 'hr',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'a'
]
ALLOWED_HTML_ATTRIBUTES = {
    'a': ['href', 'title', 'rel', 'target'],
    'span': ['class'],
    'div': ['class'],
    'p': ['class'],
}

def sanitize_description(raw_html):
    if not raw_html:
        return ''
    return bleach.clean(
        raw_html,
        tags=ALLOWED_HTML_TAGS,
        attributes=ALLOWED_HTML_ATTRIBUTES,
        strip=True
    )

def parse_and_validate_price(price_raw):
    if not price_raw:
        return None, "Price cannot be empty."
    try:
        clean_str = str(price_raw).replace(',', '').replace('₹', '').strip()
        val = decimal.Decimal(clean_str)
        if val <= 0:
            return None, "Price must be a positive number greater than ₹0."
        if val > decimal.Decimal('999999999999.99'):
            return None, "Price exceeds platform maximum allowable amount."
        return val, None
    except (decimal.InvalidOperation, ValueError, TypeError):
        return None, "Please enter a valid numeric price amount (e.g. 15000)."

def validate_phone_number(phone_raw):
    if not phone_raw:
        return None, "Phone number cannot be empty."
    clean_phone = phone_raw.strip()
    digits = re.sub(r'[^\d]', '', clean_phone)
    if len(digits) < 10 or len(digits) > 15:
        return None, "Please enter a valid 10-digit mobile number."
    return clean_phone, None

ALLOWED_IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

def validate_uploaded_image(file_obj):
    name = file_obj.name.lower()
    ext = os.path.splitext(name)[1]
    if ext not in ALLOWED_IMAGE_EXTS:
        return False, f"File '{file_obj.name}' is not an accepted image format (JPG, PNG, WEBP, GIF only)."
    if file_obj.size > MAX_IMAGE_SIZE_BYTES:
        return False, f"File '{file_obj.name}' exceeds the maximum allowed size of 10MB."
    try:
        file_obj.seek(0)
        with Image.open(file_obj) as img:
            img.verify()
        file_obj.seek(0)
    except Exception:
        return False, f"File '{file_obj.name}' is corrupted or not a valid image."
    return True, None
# Create your views here.

# Post ads view
@login_required(login_url='login')
def post_ads(request):
    if request.method == 'POST':
        # Part 1: Common Required Fields
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        category_val = request.POST.get('category', '').strip()
        price_val = request.POST.get('price', '').strip()
        condition = request.POST.get('condition', 'Good').strip()
        state_val = request.POST.get('state', '').strip()
        city_val = request.POST.get('city', '').strip()
        area = request.POST.get('area', '').strip()
        seller_name = request.POST.get('seller_name', '').strip()
        if not seller_name:
            seller_name = request.user.get_full_name() or request.user.username
        phone = request.POST.get('phone', '').strip()

        # Part 1: Common Optional Fields
        brand = request.POST.get('brand', '').strip()
        is_negotiable_val = request.POST.get('is_negotiable', 'false').lower()
        is_negotiable = is_negotiable_val in ['true', '1', 'yes', 'on']
        purchase_year = request.POST.get('purchase_year', '').strip()
        reason_for_selling = request.POST.get('reason_for_selling', '').strip()
        bill_or_warranty = request.POST.get('bill_or_warranty', '').strip()
        exchange_val = request.POST.get('exchange_accepted', 'false').lower()
        exchange_accepted = exchange_val in ['true', '1', 'yes', 'on']
        preferred_contact = request.POST.get('preferred_contact', 'Any').strip()
        preferred_contact_time = request.POST.get('preferred_contact_time', '').strip()
        delivery_available = request.POST.get('delivery_available', 'Pickup Only').strip()
        video = request.POST.get('video', '').strip()
        seller_type = request.POST.get('seller_type', 'Owner').strip() or 'Owner'
        test_ride_val = request.POST.get('test_ride_available', 'false').lower()
        test_ride_available = test_ride_val in ['true', '1', 'yes', 'on']
        registration_number = request.POST.get('registration_number', '').strip()

        # Part 2: Category Extra Specifications
        extra_details_raw = request.POST.get('extra_details', '{}')
        extra_details = {}
        if extra_details_raw:
            try:
                extra_details = json.loads(extra_details_raw)
            except Exception:
                extra_details = {}

        # Fallback for Brand if in extra_details
        if not brand:
            brand = extra_details.get('Brand') or extra_details.get('brand', '')

        # Check RC verification
        rc_status = extra_details.get('RC Available') or extra_details.get('Original RC Available') or ''
        is_rc_verified = 'yes' in str(rc_status).lower() or 'original' in str(rc_status).lower()

        # Photos validation: Minimum 3, Maximum 10 photos
        uploaded_images = []
        length_val = request.POST.get('length')
        if length_val and length_val.isdigit():
            for file_num in range(0, int(length_val)):
                img = request.FILES.get(f'images{file_num}')
                if img:
                    uploaded_images.append(img)
        if not uploaded_images and 'images' in request.FILES:
            uploaded_images = request.FILES.getlist('images')

        # Minimum 3 photos check (as per specification)
        if len(uploaded_images) < 3:
            return JsonResponse({
                'status': 'error',
                'message': 'Please upload at least 3 photos (Minimum 3, Maximum 10 photos required).'
            }, status=400)

        if len(uploaded_images) > 10:
            return JsonResponse({
                'status': 'error',
                'message': 'Maximum 10 photos are allowed.'
            }, status=400)

        # Validate each uploaded image (file type, size <= 10MB, PIL verification)
        for img in uploaded_images:
            is_valid, img_err = validate_uploaded_image(img)
            if not is_valid:
                return JsonResponse({'status': 'error', 'message': img_err}, status=400)

        # Basic validations
        if not title:
            return JsonResponse({'status': 'error', 'message': 'Title cannot be empty.'}, status=400)
        
        # Sanitize HTML description (Stored XSS prevention)
        description = sanitize_description(description)
        if not description.strip():
            return JsonResponse({'status': 'error', 'message': 'Description cannot be empty.'}, status=400)
        
        if not category_val:
            return JsonResponse({'status': 'error', 'message': 'Category must be selected.'}, status=400)
        
        # Price validation (prevents 500 error on bad/invalid price input)
        price_amount, price_err = parse_and_validate_price(price_val)
        if price_err:
            return JsonResponse({'status': 'error', 'message': price_err}, status=400)
        
        # Phone number validation
        clean_phone, phone_err = validate_phone_number(phone)
        if phone_err:
            return JsonResponse({'status': 'error', 'message': phone_err}, status=400)

        # Resolve category (prevents arbitrary category creation by users)
        c = None
        if category_val:
            if category_val.isdigit():
                c = Category.objects.filter(id=int(category_val)).first()
            if not c:
                c = Category.objects.filter(slug=category_val).first()
            if not c:
                c = Category.objects.filter(category_name__iexact=category_val).first()
        if not c:
            return JsonResponse({'status': 'error', 'message': 'Please select a valid category from the list.'}, status=400)

        # Resolve state and city (prevents arbitrary state creation by users)
        s = None
        if state_val:
            if state_val.isdigit():
                s = State.objects.filter(id=int(state_val)).first()
            if not s:
                s = State.objects.filter(state_name__iexact=state_val).first()
            if not s:
                s = State.objects.filter(slug__iexact=state_val).first()

        ci = None
        if city_val:
            ci = City.objects.filter(city_name__iexact=city_val).first()
            if not ci:
                ci = City.objects.create(city_name=city_val)

        author, _ = Author.objects.get_or_create(user=request.user)

        # Create Ad
        ads = Ads.objects.create(
            author=author,
            title=title,
            description=description,
            price=price_amount,
            category=c,
            condition=condition,
            state=s,
            city=ci,
            area=area,
            seller_name=seller_name,
            brand=brand,
            phone=clean_phone,
            is_phone_verified=True,
            video=video if video else None,
            is_negotiable=is_negotiable,
            purchase_year=purchase_year,
            reason_for_selling=reason_for_selling,
            bill_or_warranty=bill_or_warranty,
            exchange_accepted=exchange_accepted,
            preferred_contact=preferred_contact,
            preferred_contact_time=preferred_contact_time,
            delivery_available=delivery_available,
            seller_type=seller_type,
            test_ride_available=test_ride_available,
            registration_number=registration_number,
            is_rc_verified=is_rc_verified,
            extra_details=extra_details,
            is_active=True
        )

        for img in uploaded_images:
            AdsImages.objects.create(ads=ads, image=img)

        # Send email notification to Admin safely
        try:
            mail_subject = "New Ads submitted"
            sender_email = request.user.email
            message = f"Dear Admin, you received a new ads request from {sender_email} for '{title}'"
            to_email = settings.EMAIL_HOST_USER
            from_email = settings.EMAIL_HOST_USER
            if to_email:
                send_mail(
                    mail_subject,
                    message,
                    from_email,
                    [to_email],
                    fail_silently=True,
                )
        except Exception:
            pass

        return JsonResponse({
            'status': 'success',
            'message': 'Your Ad has been posted successfully!',
            'ad_id': ads.id,
            'redirect_url': reverse('ads-detail', kwargs={'pk': ads.id})
        })

    states = State.objects.all().order_by('state_name')
    categories = Category.objects.filter(parent__isnull=True).prefetch_related('subcategories').order_by('id')
    
    # Build category hierarchy JSON for dynamic UI
    cat_tree = []
    for cat in categories:
        subs = [{'id': sub.id, 'name': sub.category_name, 'slug': sub.slug} for sub in cat.subcategories.all()]
        cat_tree.append({
            'id': cat.id,
            'name': cat.category_name,
            'slug': cat.slug,
            'subcategories': subs
        })

    context = {
        'states': states,
        'categories': categories,
        'categories_json': json.dumps(cat_tree),
    }
    return render(request, 'ads/post-ads.html', context)

# Ads listing view
def ads_listing(request):
    ads_qs = (
        Ads.objects.filter(is_active=True)
        .select_related('author', 'author__user', 'category', 'category__parent', 'city', 'state')
        .prefetch_related('adsimages_set')
        .order_by('-date_created')
    )

    total_ads_count = ads_qs.count()

    # 12 products per page
    paginator = Paginator(ads_qs, 12)
    page_number = request.GET.get('page', 1)

    try:
        ads_listing_page = paginator.get_page(page_number)
    except (PageNotAnInteger, EmptyPage):
        ads_listing_page = paginator.get_page(1)

    # Smart elided page range (e.g. 1 2 3 ... 38)
    elided_page_range = paginator.get_elided_page_range(
        ads_listing_page.number, on_each_side=2, on_ends=1
    )

    category_listing = (
        Category.objects.filter(parent__isnull=True)
        .prefetch_related('subcategories')
        .annotate(total_ads=Count('ads'))
        .order_by('id')
    )

    context = {
        'ads_listing': ads_listing_page,
        'page_obj': ads_listing_page,
        'paginator': paginator,
        'elided_page_range': elided_page_range,
        'total_ads_count': total_ads_count,
        'category_listing': category_listing
    }

    return render(request, 'ads/ads-listing.html', context)

# Ads detail view
def ads_detail(request, pk):
    ads_detail = get_object_or_404(Ads, pk=pk)

    # Inactive check: staff, author, or users who have this item in their wishlist may view it
    if not ads_detail.is_active:
        is_authorized = (
            request.user.is_authenticated and (
                request.user.is_staff or 
                (ads_detail.author and ads_detail.author.user == request.user) or
                Wishlist.objects.filter(user=request.user, ad=ads_detail).exists()
            )
        )
        if not is_authorized:
            raise Http404("This listing is inactive or has been delisted.")

    ads_photos = AdsImages.objects.filter(ads=ads_detail)

    extra = ads_detail.extra_details or {}

    # Category name for context checks
    cat_name = ""
    if ads_detail.category:
        cat_name = ads_detail.category.category_name
        if ads_detail.category.parent:
            cat_name = f"{ads_detail.category.parent.category_name} - {cat_name}"
    cat_lower = cat_name.lower()

    # Partition classification keywords
    condition_keywords = [
        'condition', 'accident', 'tyre', 'battery health', 'battery condition', 'engine condition',
        'scratches', 'dents', 'parts changed', 'repaired', 'last service', 'service record',
        'working', 'screen condition', 'flaws', 'rust', 'defects', 'usage status'
    ]

    document_keywords = [
        'rc', 'insurance', 'puc', 'loan', 'hypothecation', 'noc', 'keys', 'registration year',
        'permit', 'fitness', 'road tax', 'title', 'rera', 'possession', 'bill', 'warranty',
        'authenticity', 'invoice', 'gst'
    ]

    feature_keys = [
        'key features', 'features', 'accessories included', 'modifications done',
        'society amenities', 'included', 'extras', 'highlights'
    ]

    partition_specs = {}
    partition_condition = {}
    partition_documents = {}
    features_list = []

    for k, v in extra.items():
        if not v or k == 'Registration Number (Private)':
            continue
        k_lower = k.lower()

        # Check if it's a feature bundle
        if any(fk in k_lower for fk in feature_keys):
            items = [item.strip() for item in str(v).replace('\n', ',').split(',') if item.strip()]
            features_list.extend(items)
            continue

        # Check if condition
        if any(ck in k_lower for ck in condition_keywords) and not ('road' in k_lower and 'tax' in k_lower):
            partition_condition[k] = v
        # Check if document
        elif any(dk in k_lower for dk in document_keywords):
            partition_documents[k] = v
        else:
            partition_specs[k] = v

    # Fallback if condition details empty, add overall condition
    if not partition_condition and ads_detail.condition:
        partition_condition['Overall Condition'] = ads_detail.condition

    # Category-specific Safety Tips & Advice
    if any(term in cat_lower for term in ['car', 'bike', 'motorcycle', 'scooter', 'truck', 'tempo', 'bus', 'tractor', 'vehicle']):
        safety_title = "Vehicle Buyer Inspection & Safety Tips"
        safety_tips = [
            "Meet seller in an open, daylight public area (e.g. near a local RTO or police station).",
            "Take an extensive test ride/drive to check brakes, gears, suspension, and engine sound.",
            "Physically verify chassis number and engine number stamped on the vehicle with the RC.",
            "Verify insurance validity and check Parivahan / mParivahan app for pending challans.",
            "Never transfer an advance token before physically inspecting the vehicle and original documents."
        ]
    elif any(term in cat_lower for term in ['mobile', 'phone', 'tablet', 'smartwatch', 'laptop', 'camera', 'electronic', 'tv', 'appliance']):
        safety_title = "Electronics & Gadgets Verification Tips"
        safety_tips = [
            "Meet in a cafe or safe public location with Wi-Fi to test the device thoroughly.",
            "Dial *#06# to verify IMEI matches the box and bill. Check IMEI against blacklist registers.",
            "Ensure seller logs out of Apple ID / iCloud / Google account and factory resets in front of you.",
            "Test touch response across all screen edges, camera autofocus, speaker, microphone, and charging port.",
            "Check battery health percentage and inspect for any screen replacement or water damage indicators."
        ]
    elif 'propert' in cat_lower:
        safety_title = "Property Buyer Due Diligence Guide"
        safety_tips = [
            "Always inspect original Title Deeds (7/12 extract, Index II, Sale Deed) through an advocate.",
            "Verify the RERA registration number and approved building layout plan on the state RERA portal.",
            "Check for an Encumbrance Certificate (EC) for the last 15-30 years to ensure clean title without bank loans.",
            "Verify with the society office that all maintenance charges and property taxes are fully paid.",
            "Only transact via formal banking channels with official stamped agreement to sell."
        ]
    elif any(term in cat_lower for term in ['furniture', 'home']):
        safety_title = "Furniture Inspection Guide"
        safety_tips = [
            "Inspect physical wood joints, hinges, drawer slides, and support legs for wobble or cracks.",
            "Check corners and undersides thoroughly for signs of moisture damage, mold, or termite dust.",
            "Measure your room, staircase, and doorway clearances to ensure the piece fits smoothly.",
            "Negotiate delivery/moving arrangements and inspect after loading onto the transport vehicle."
        ]
    else:
        safety_title = "PreLoved Safe Marketplace Tips"
        safety_tips = [
            "Always meet the seller in person in a safe, public daylight location.",
            "Inspect the item thoroughly and verify all functions before finalizing the purchase.",
            "Never share bank OTP, UPI PIN, or scan unknown QR codes sent by buyers or sellers.",
            "Never make advance payments for shipping or holding an item without seeing it first."
        ]

    has_requested_call = False
    if request.user.is_authenticated:
        has_requested_call = CallRequest.objects.filter(ad=ads_detail, buyer=request.user).exists()

    context = {
        'ads_detail': ads_detail,
        'ads_photos': ads_photos,
        'partition_specs': partition_specs,
        'partition_condition': partition_condition,
        'partition_documents': partition_documents,
        'features_list': features_list,
        'safety_title': safety_title,
        'safety_tips': safety_tips,
        'has_requested_call': has_requested_call,
    }

    return render(request, 'ads/ads-detail.html', context)

# Ads category archive view
def ads_category_archive(request, slug):
    category = get_object_or_404(Category, slug=slug)
    subcategories = category.subcategories.all()
    if subcategories.exists():
        ads_by_category = Ads.objects.filter(Q(category=category) | Q(category__in=subcategories), is_active=True).distinct()
    else:
        ads_by_category = Ads.objects.filter(category=category, is_active=True)

    context = {
        'category' : category,
        'ads_by_category' : ads_by_category,
        'subcategories': subcategories
    }

    return render(request, 'ads/category-archive.html', context)

# Ads state archive view
def ads_state_archive(request, slug):
    state = get_object_or_404(State, slug=slug)
    ads_by_state = Ads.objects.filter(state=state, is_active=True)

    context = {
        'state' : state,
        'ads_by_state' : ads_by_state
    }

    return render(request, 'ads/state-archive.html', context)

# Ads city archive view
def ads_city_archive(request, slug):
    cities = City.objects.filter(slug=slug)
    if not cities.exists():
        raise Http404("City not found")
    city = cities.first()
    ads_by_city = (
        Ads.objects.filter(city__in=cities, is_active=True)
        .select_related('category', 'category__parent', 'state', 'city', 'author__user')
        .prefetch_related('adsimages_set')
        .order_by('-id')
    )

    context = {
        'city': city,
        'ads_by_city': ads_by_city
    }

    return render(request, 'ads/city-archive.html', context)

# Ads author archive view
def ads_author_archive(request, pk):
    author = get_object_or_404(Author, pk=pk)
    ads_by_author = Ads.objects.filter(author=author, is_active=True)

    context = {
        'author' : author,
        'ads_by_author' : ads_by_author
    }

    return render(request, 'ads/author-archive.html', context)

# Ads search/filter view
def ads_search(request):
    state = request.GET.get('state_name') or request.GET.get('state') or ''
    category = request.GET.get('category_name') or request.GET.get('category') or request.GET.get('cat') or ''
    customword = (
        request.GET.get('customword') or
        request.GET.get('q') or
        request.GET.get('keyword') or
        request.GET.get('search') or
        request.GET.get('s') or
        ''
    ).strip()

    ads_search_result = (
        Ads.objects.filter(is_active=True)
        .select_related('category', 'category__parent', 'state', 'city', 'author__user')
        .prefetch_related('adsimages_set')
    )

    # State filter
    if state and state.strip() and state.strip().lower() not in ['select state', 'all states (india)', 'all states', 'all']:
        s_val = state.strip()
        ads_search_result = ads_search_result.filter(
            Q(state__state_name__iexact=s_val) | Q(state__slug__iexact=s_val)
        )

    # Category filter
    if category and category.strip() and category.strip().lower() not in ['select category', 'all categories', 'all']:
        c_val = category.strip()
        if c_val.endswith(' (All)'):
            c_val = c_val[:-6].strip()

        cat_obj = Category.objects.filter(
            Q(category_name__iexact=c_val) | Q(slug__iexact=c_val)
        ).first()

        if cat_obj:
            if cat_obj.subcategories.exists():
                ads_search_result = ads_search_result.filter(
                    Q(category=cat_obj) | Q(category__in=cat_obj.subcategories.all())
                )
            else:
                ads_search_result = ads_search_result.filter(category=cat_obj)
        else:
            ads_search_result = ads_search_result.filter(
                Q(category__category_name__icontains=c_val) | Q(category__slug__icontains=c_val)
            )

    # Multi-term Intelligent Keyword Search
    if customword:
        words = customword.split()
        stopwords = {'in', 'at', 'for', 'of', 'and', 'the', 'with', 'a', 'an', 'to', 'near'}
        if len(words) > 1:
            search_terms = [w for w in words if w.lower() not in stopwords] or words
        else:
            search_terms = words

        for term in search_terms:
            ads_search_result = ads_search_result.filter(
                Q(title__icontains=term) |
                Q(description__icontains=term) |
                Q(brand__icontains=term) |
                Q(category__category_name__icontains=term) |
                Q(category__parent__category_name__icontains=term) |
                Q(city__city_name__icontains=term) |
                Q(state__state_name__icontains=term) |
                Q(area__icontains=term) |
                Q(condition__icontains=term)
            )

    ads_search_result = ads_search_result.order_by('-id').distinct()

    context = {
        'ads_search_result': ads_search_result,
        'state_name': state,
        'category_name': category,
        'customword': customword,
    }

    return render(request, 'ads/ads-search.html', context)

# Ads edit view
@login_required(login_url='login')
def ads_edit(request, pk):
    ad = get_object_or_404(
        Ads.objects.select_related('author', 'author__user', 'category', 'category__parent', 'city', 'state'),
        pk=pk
    )

    # Permission check: owner or staff/superuser
    if ad.author and ad.author.user != request.user and not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Permission denied: You can only edit your own classified listings.")
        return redirect('dashboard')

    if request.method == 'POST':
        # Part 1: Common Required Fields
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        category_val = request.POST.get('category', '').strip()
        price_val = request.POST.get('price', '').strip()
        condition = request.POST.get('condition', ad.condition).strip()
        state_val = request.POST.get('state', '').strip()
        city_val = request.POST.get('city', '').strip()
        area = request.POST.get('area', '').strip()
        seller_name = request.POST.get('seller_name', '').strip()
        phone = request.POST.get('phone', '').strip()

        # Part 1: Common Optional Fields
        brand = request.POST.get('brand', '').strip()
        is_negotiable_val = request.POST.get('is_negotiable', 'false').lower()
        is_negotiable = is_negotiable_val in ['true', '1', 'yes', 'on']
        purchase_year = request.POST.get('purchase_year', '').strip()
        reason_for_selling = request.POST.get('reason_for_selling', '').strip()
        bill_or_warranty = request.POST.get('bill_or_warranty', '').strip()
        exchange_val = request.POST.get('exchange_accepted', 'false').lower()
        exchange_accepted = exchange_val in ['true', '1', 'yes', 'on']
        preferred_contact = request.POST.get('preferred_contact', 'Any').strip()
        preferred_contact_time = request.POST.get('preferred_contact_time', '').strip()
        delivery_available = request.POST.get('delivery_available', 'Pickup Only').strip()
        video = request.POST.get('video', '').strip()
        seller_type = request.POST.get('seller_type', 'Owner').strip() or 'Owner'
        test_ride_val = request.POST.get('test_ride_available', 'false').lower()
        test_ride_available = test_ride_val in ['true', '1', 'yes', 'on']
        registration_number = request.POST.get('registration_number', '').strip()

        # Status Toggles
        is_sold_val = request.POST.get('is_sold', 'false').lower()
        is_sold = is_sold_val in ['true', '1', 'yes', 'on']
        is_active_val = request.POST.get('is_active', 'false').lower()
        is_active = is_active_val in ['true', '1', 'yes', 'on']

        # Extra Specifications
        extra_details_raw = request.POST.get('extra_details', '')
        extra_details = dict(ad.extra_details) if ad.extra_details else {}
        if extra_details_raw:
            try:
                extra_details = json.loads(extra_details_raw)
            except Exception:
                pass

        # Allow individual extra fields posted from form
        for key, val in request.POST.items():
            if key.startswith('extra_spec_') and val.strip():
                spec_name = key.replace('extra_spec_', '').replace('-', ' ').title()
                extra_details[spec_name] = val.strip()

        # Fallback for Brand if in extra_details
        if not brand:
            brand = extra_details.get('Brand') or extra_details.get('brand', '')

        # RC Verification check
        rc_status = extra_details.get('RC Available') or extra_details.get('Original RC Available') or ''
        is_rc_verified = 'yes' in str(rc_status).lower() or 'original' in str(rc_status).lower()

        # Check AJAX
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == '1'

        if not title:
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': 'Title cannot be empty.'}, status=400)
            messages.error(request, 'Title cannot be empty.')
            return redirect('ads-edit', pk=ad.pk)
        
        # Sanitize HTML description (Stored XSS prevention)
        description = sanitize_description(description)
        if not description.strip():
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': 'Description cannot be empty.'}, status=400)
            messages.error(request, 'Description cannot be empty.')
            return redirect('ads-edit', pk=ad.pk)
        
        # Price validation
        price_amount, price_err = parse_and_validate_price(price_val)
        if price_err:
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': price_err}, status=400)
            messages.error(request, price_err)
            return redirect('ads-edit', pk=ad.pk)
        
        # Phone validation
        clean_phone, phone_err = validate_phone_number(phone)
        if phone_err:
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': phone_err}, status=400)
            messages.error(request, phone_err)
            return redirect('ads-edit', pk=ad.pk)

        # Handle New Uploaded Photos
        uploaded_images = []
        length_val = request.POST.get('length')
        if length_val and length_val.isdigit():
            for file_num in range(0, int(length_val)):
                img = request.FILES.get(f'images{file_num}')
                if img:
                    uploaded_images.append(img)
        if not uploaded_images and 'images' in request.FILES:
            uploaded_images = request.FILES.getlist('images')

        # Validate newly uploaded images
        for img in uploaded_images:
            is_valid, img_err = validate_uploaded_image(img)
            if not is_valid:
                if is_ajax:
                    return JsonResponse({'status': 'error', 'message': img_err}, status=400)
                messages.error(request, img_err)
                return redirect('ads-edit', pk=ad.pk)

        # Handle Photo Deletions and minimum photo rule
        delete_image_ids = request.POST.getlist('delete_images')
        existing_count = AdsImages.objects.filter(ads=ad).exclude(id__in=delete_image_ids).count()
        total_photos_count = existing_count + len(uploaded_images)
        if total_photos_count < 1:
            err_msg = 'A listing must retain at least one product photo. Please upload a new photo before deleting all existing ones.'
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': err_msg}, status=400)
            messages.error(request, err_msg)
            return redirect('ads-edit', pk=ad.pk)

        if delete_image_ids:
            AdsImages.objects.filter(ads=ad, id__in=delete_image_ids).delete()

        for img in uploaded_images:
            AdsImages.objects.create(ads=ad, image=img)

        # Resolve category if changed (prevent arbitrary category creation)
        if category_val:
            c = None
            if category_val.isdigit():
                c = Category.objects.filter(id=int(category_val)).first()
            if not c:
                c = Category.objects.filter(slug=category_val).first()
            if not c:
                c = Category.objects.filter(category_name__iexact=category_val).first()
            if c:
                ad.category = c

        # Resolve State & City
        if state_val:
            s = None
            if state_val.isdigit():
                s = State.objects.filter(id=int(state_val)).first()
            if not s:
                s = State.objects.filter(state_name__iexact=state_val).first()
            if not s:
                s = State.objects.filter(slug__iexact=state_val).first()
            if s:
                ad.state = s
        if city_val:
            ci = City.objects.filter(city_name__iexact=city_val).first()
            if not ci:
                ci = City.objects.create(city_name=city_val)
            ad.city = ci

        # Update attributes
        ad.title = title
        ad.description = description
        ad.price = price_amount
        ad.condition = condition
        ad.area = area
        if seller_name:
            ad.seller_name = seller_name
        ad.phone = clean_phone
        ad.brand = brand
        ad.is_negotiable = is_negotiable
        ad.purchase_year = purchase_year
        ad.reason_for_selling = reason_for_selling
        ad.bill_or_warranty = bill_or_warranty
        ad.exchange_accepted = exchange_accepted
        ad.preferred_contact = preferred_contact
        ad.preferred_contact_time = preferred_contact_time
        ad.delivery_available = delivery_available
        ad.seller_type = seller_type
        ad.test_ride_available = test_ride_available
        ad.registration_number = registration_number
        ad.is_rc_verified = is_rc_verified
        ad.extra_details = extra_details
        ad.video = video if video else None
        ad.is_sold = is_sold
        ad.is_active = is_active
        ad.save()

        success_msg = f"Listing '{ad.title}' has been successfully updated!"
        if is_ajax:
            return JsonResponse({
                'status': 'success',
                'message': success_msg,
                'ad_id': ad.id,
                'redirect_url': reverse('ads-detail', kwargs={'pk': ad.id})
            })

        messages.success(request, success_msg)
        return redirect('ads-detail', pk=ad.pk)

    # GET Request: Prepare context
    states = State.objects.all().order_by('state_name')
    categories = Category.objects.filter(parent__isnull=True).prefetch_related('subcategories').order_by('id')
    existing_images = ad.adsimages_set.all()

    # Build category hierarchy JSON for dynamic UI
    cat_tree = []
    for cat in categories:
        subs = [{'id': sub.id, 'name': sub.category_name, 'slug': sub.slug} for sub in cat.subcategories.all()]
        cat_tree.append({
            'id': cat.id,
            'name': cat.category_name,
            'slug': cat.slug,
            'subcategories': subs
        })

    # Find active parent category
    current_parent_category = None
    if ad.category:
        if ad.category.parent:
            current_parent_category = ad.category.parent
        else:
            current_parent_category = ad.category

    context = {
        'ad': ad,
        'existing_images': existing_images,
        'states': states,
        'categories': categories,
        'categories_json': json.dumps(cat_tree),
        'current_parent_category': current_parent_category,
    }
    return render(request, 'ads/edit-ad.html', context)


# Ads delete view
@login_required(login_url='login')
def ads_delete(request, pk):
    ad = get_object_or_404(Ads, pk=pk)
    if ad.author and ad.author.user != request.user and not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "Permission denied: You can only delete your own listings.")
        return redirect("dashboard")
    ad.delete()
    messages.success(request, "Listing has been successfully deleted.")
    return redirect("dashboard")


# User Wishlist Page View
@login_required(login_url='login')
def wishlist_view(request):
    wishlist_items = (
        Wishlist.objects.filter(user=request.user)
        .select_related('ad', 'ad__category', 'ad__category__parent', 'ad__city', 'ad__state', 'ad__author__user')
        .prefetch_related('ad__adsimages_set')
        .order_by('-date_added')
    )

    total_count = wishlist_items.count()
    sold_count = sum(1 for it in wishlist_items if it.ad.is_sold_out)
    active_count = total_count - sold_count

    context = {
        'wishlist_items': wishlist_items,
        'total_count': total_count,
        'active_count': active_count,
        'sold_count': sold_count,
    }
    return render(request, 'ads/wishlist.html', context)


# Toggle Wishlist Item (AJAX + Form fallback)
def wishlist_toggle(request, pk):
    if not request.user.is_authenticated:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
            return JsonResponse({
                'status': 'unauthenticated',
                'message': 'Please log in to add items to your wishlist.',
                'redirect_url': reverse('login') + f'?next={request.path}'
            }, status=401)
        messages.warning(request, "Please log in to add items to your wishlist.")
        return redirect('login')

    ad = get_object_or_404(Ads, pk=pk)
    wishlist_item = Wishlist.objects.filter(user=request.user, ad=ad).first()

    if wishlist_item:
        wishlist_item.delete()
        in_wishlist = False
        action = 'removed'
        msg = f"'{ad.title[:25]}...' removed from your Wishlist."
    else:
        Wishlist.objects.create(user=request.user, ad=ad)
        in_wishlist = True
        action = 'added'
        msg = f"'{ad.title[:25]}...' saved to your Wishlist!"

    total_wishlist_count = Wishlist.objects.filter(user=request.user).count()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json' or request.POST.get('format') == 'json':
        return JsonResponse({
            'status': 'success',
            'action': action,
            'in_wishlist': in_wishlist,
            'wishlist_count': total_wishlist_count,
            'message': msg
        })

    messages.success(request, msg)
    next_url = request.META.get('HTTP_REFERER') or reverse('wishlist')
    return redirect(next_url)


# Remove Item from Wishlist View
@login_required(login_url='login')
def wishlist_remove(request, pk):
    # pk can be Wishlist ID or Ads ID
    item = Wishlist.objects.filter(user=request.user, pk=pk).first()
    if not item:
        item = Wishlist.objects.filter(user=request.user, ad_id=pk).first()

    if item:
        ad_title = item.ad.title
        item.delete()
        messages.success(request, f"'{ad_title[:30]}' was removed from your Wishlist.")
    else:
        messages.info(request, "Item was not found in your Wishlist.")

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        count = Wishlist.objects.filter(user=request.user).count()
        return JsonResponse({'status': 'success', 'wishlist_count': count})

    return redirect('wishlist')


# Request a Call / Callback View
@require_POST
def request_call(request, pk):
    ad = get_object_or_404(Ads, pk=pk)

    if not ad.is_active or ad.is_sold:
        return JsonResponse({'status': 'error', 'message': 'This listing is no longer available for callback.'}, status=400)

    if request.user.is_authenticated and ad.author and ad.author.user == request.user:
        return JsonResponse({'status': 'error', 'message': 'You cannot request a callback on your own listing.'}, status=400)

    buyer_name = request.POST.get('buyer_name', '').strip()
    buyer_phone = request.POST.get('buyer_phone', '').strip()
    preferred_time = request.POST.get('preferred_time', 'Anytime').strip()
    message_text = request.POST.get('message', '').strip()

    if not buyer_name:
        if request.user.is_authenticated:
            buyer_name = request.user.get_full_name() or request.user.username
        else:
            return JsonResponse({'status': 'error', 'message': 'Please provide your full name.'}, status=400)

    clean_phone, phone_err = validate_phone_number(buyer_phone)
    if phone_err:
        return JsonResponse({'status': 'error', 'message': phone_err}, status=400)

    seller_user = ad.author.user if ad.author else None
    if not seller_user:
        return JsonResponse({'status': 'error', 'message': 'Seller information is currently unavailable.'}, status=400)

    # Prevent spamming: Check if same phone requested callback on same ad in last 10 minutes
    ten_mins_ago = timezone.now() - datetime.timedelta(minutes=10)
    already_requested = CallRequest.objects.filter(
        ad=ad,
        buyer_phone=clean_phone,
        created_at__gte=ten_mins_ago
    ).exists()

    if already_requested:
        return JsonResponse({
            'status': 'success',
            'already_sent': True,
            'message': 'Callback request received! The seller already has your contact details and will call you soon.'
        })

    call_req = CallRequest.objects.create(
        ad=ad,
        seller=seller_user,
        buyer=request.user if request.user.is_authenticated else None,
        buyer_name=buyer_name,
        buyer_phone=clean_phone,
        preferred_time=preferred_time or 'Anytime',
        message=message_text
    )

    # Send email notification to seller safely
    if seller_user.email:
        try:
            subject = f"PreLoved: New Call Request for '{ad.title[:45]}'"
            body = (
                f"Hello {ad.seller_name or seller_user.username},\n\n"
                f"You have received a new Call Request on your PreLoved listing:\n"
                f"Listing: {ad.title}\n\n"
                f"Buyer Details:\n"
                f"- Name: {buyer_name}\n"
                f"- Phone: {clean_phone}\n"
                f"- Preferred Time: {preferred_time}\n"
                f"- Message: {message_text or 'No message provided'}\n\n"
                f"Please contact the buyer directly.\n\n"
                f"Best regards,\n"
                f"PreLoved Team"
            )
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@preloved.com')
            send_mail(subject, body, from_email, [seller_user.email], fail_silently=True)
        except Exception:
            pass

    seller_display = ad.seller_name or seller_user.username
    return JsonResponse({
        'status': 'success',
        'message': f"Your call request has been sent! {seller_display} has been notified to call you at {clean_phone}."
    })










