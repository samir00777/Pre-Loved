import json
import csv
from datetime import datetime
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum
from django.http import JsonResponse, HttpResponse

from ads.models import Ads, Category, Author, State, City
from django.contrib.auth.models import User
from .services import NextAdminManager

class AdminBaseMixin:
    """Base mixin to enforce staff/admin authentication and inject global context."""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            login_url = reverse('custom_admin:login')
            next_url = request.get_full_path()
            return redirect(f"{login_url}?next={next_url}")
        if not (request.user.is_staff or request.user.is_superuser):
            messages.error(request, "Access restricted: Administrator or Staff privileges are required.")
            return redirect('custom_admin:login')
        return super().dispatch(request, *args, **kwargs)

    def get_common_context(self):
        user = getattr(self, 'request', None) and self.request.user
        display_name = "Samir Karavadara"
        role = "Super Admin"
        email = "samir@preloved.in"
        avatar = "/static/images/default.jpg"

        if user and user.is_authenticated:
            full = user.get_full_name()
            display_name = full if full else user.username
            role = "Super Admin" if user.is_superuser else "Staff Administrator"
            email = user.email or f"{user.username}@preloved.in"
            if hasattr(user, 'author') and user.author.profile_pic:
                avatar = user.author.profile_pic.url

        return {
            "admin_user": {
                "name": display_name,
                "role": role,
                "email": email,
                "avatar": avatar
            },
            "unread_notifications": 4,
            "total_ads_count": Ads.objects.count(),
        }

class AdminLoginView(View):
    """Admin Login Portal with UI styled matching PreLoved website."""
    def get(self, request):
        if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
            return redirect(request.GET.get('next') or 'custom_admin:dashboard')
        return render(request, "custom_admin/login.html", {
            "next": request.GET.get('next', '/admin/')
        })

    def post(self, request):
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        next_url = request.POST.get('next') or request.GET.get('next') or '/admin/'

        if not username or not password:
            messages.error(request, "Please enter both username and password.")
            return render(request, "custom_admin/login.html", {"next": next_url, "username": username})

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.is_staff or user.is_superuser:
                login(request, user)
                messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
                return redirect(next_url)
            else:
                messages.error(request, "Access restricted: This account does not have administrator privileges.")
                return render(request, "custom_admin/login.html", {"next": next_url, "username": username})
        else:
            messages.error(request, "Invalid username or password. Please verify credentials.")
            return render(request, "custom_admin/login.html", {"next": next_url, "username": username})

class AdminLogoutView(View):
    """Admin Logout."""
    def get(self, request):
        logout(request)
        messages.info(request, "You have been safely signed out.")
        return redirect('custom_admin:login')

class AdminDashboardView(AdminBaseMixin, View):
    """NextAdmin Main Dashboard View replicating all 7 components."""
    def get(self, request):
        stats = NextAdminManager.get_overview_stats()
        sales_chart = NextAdminManager.get_sales_chart_data()
        inventory = NextAdminManager.get_inventory_overview()
        top_products = NextAdminManager.get_top_products(limit=5)
        category_distribution = NextAdminManager.get_category_distribution()
        regional_distribution = NextAdminManager.get_regional_distribution()
        recent_transactions = NextAdminManager.get_recent_transactions(limit=10)

        context = {
            **self.get_common_context(),
            "active_tab": "dashboard",
            "overview_stats": stats,
            "sales_chart": sales_chart,
            "sales_chart_json": json.dumps(sales_chart),
            "inventory": inventory,
            "top_products": top_products,
            "category_distribution": category_distribution,
            "regional_distribution": regional_distribution,
            "recent_transactions": recent_transactions,
        }
        return render(request, "custom_admin/dashboard.html", context)

class AdminAdsListView(AdminBaseMixin, View):
    """All Listings Table & Filter Manager."""
    def get(self, request):
        query = request.GET.get('q', '').strip()
        cat_id = request.GET.get('category', '')
        user_id = request.GET.get('user', '').strip()
        status = request.GET.get('status', '')
        sort = request.GET.get('sort', '-id')

        ads_qs = (
            Ads.objects.all()
            .select_related('category', 'category__parent', 'author', 'author__user', 'city', 'state')
            .prefetch_related('adsimages_set')
        )

        filtered_user = None
        if user_id:
            ads_qs = ads_qs.filter(author__user_id=user_id)
            filtered_user = User.objects.filter(pk=user_id).first()

        if query:
            ads_qs = ads_qs.filter(
                Q(title__icontains=query) |
                Q(seller_name__icontains=query) |
                Q(brand__icontains=query) |
                Q(city__city_name__icontains=query) |
                Q(author__user__username__icontains=query) |
                Q(author__user__first_name__icontains=query) |
                Q(author__user__last_name__icontains=query) |
                Q(author__user__email__icontains=query)
            )

        if cat_id:
            ads_qs = ads_qs.filter(Q(category_id=cat_id) | Q(category__parent_id=cat_id))

        if status == 'active':
            ads_qs = ads_qs.filter(is_active=True)
        elif status == 'inactive':
            ads_qs = ads_qs.filter(is_active=False)
        elif status == 'featured':
            ads_qs = ads_qs.filter(is_featured=True)

        if sort in ['price', '-price', 'id', '-id', 'date_created', '-date_created']:
            ads_qs = ads_qs.order_by(sort)
        else:
            ads_qs = ads_qs.order_by('-id')

        paginator = Paginator(ads_qs, 15)
        page_num = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_num)

        categories = Category.objects.filter(parent__isnull=True).prefetch_related('subcategories')

        context = {
            **self.get_common_context(),
            "active_tab": "ads",
            "page_obj": page_obj,
            "total_count": paginator.count,
            "categories": categories,
            "current_query": query,
            "current_cat": cat_id,
            "current_status": status,
            "current_sort": sort,
            "current_user": user_id,
            "filtered_user": filtered_user,
        }
        return render(request, "custom_admin/ads_list.html", context)

class AdminAdDetailView(AdminBaseMixin, View):
    """View and Inspect Ad in NextAdmin."""
    def get(self, request, pk):
        ad = get_object_or_404(
            Ads.objects.select_related('category', 'category__parent', 'author', 'city', 'state')
            .prefetch_related('adsimages_set'),
            pk=pk
        )
        context = {
            **self.get_common_context(),
            "active_tab": "ads",
            "ad": ad,
            "images": ad.adsimages_set.all(),
            "extra_details": ad.extra_details or {}
        }
        return render(request, "custom_admin/ad_detail.html", context)

class AdminAdToggleActiveView(AdminBaseMixin, View):
    """Toggle listing active/inactive status (Supports both GET and POST)."""
    def get(self, request, pk):
        return self._toggle(request, pk)

    def post(self, request, pk):
        return self._toggle(request, pk)

    def _toggle(self, request, pk):
        ad = get_object_or_404(Ads, pk=pk)
        ad.is_active = not ad.is_active
        ad.save(update_fields=['is_active'])
        status_label = "activated" if ad.is_active else "deactivated"
        messages.success(request, f"Ad #{ad.id} '{ad.title[:30]}...' successfully {status_label}.")
        next_url = request.META.get('HTTP_REFERER') or '/admin/ads/'
        return redirect(next_url)

class AdminAdToggleFeaturedView(AdminBaseMixin, View):
    """Toggle listing featured status (Supports both GET and POST)."""
    def get(self, request, pk):
        return self._toggle(request, pk)

    def post(self, request, pk):
        return self._toggle(request, pk)

    def _toggle(self, request, pk):
        ad = get_object_or_404(Ads, pk=pk)
        ad.is_featured = not ad.is_featured
        ad.save(update_fields=['is_featured'])
        status_label = "marked as Featured" if ad.is_featured else "unmarked from Featured"
        messages.success(request, f"Ad #{ad.id} '{ad.title[:30]}...' {status_label}.")
        next_url = request.META.get('HTTP_REFERER') or '/admin/ads/'
        return redirect(next_url)

class AdminAdDeleteView(AdminBaseMixin, View):
    """Delete an ad listing."""
    def post(self, request, pk):
        ad = get_object_or_404(Ads, pk=pk)
        title = ad.title
        ad.delete()
        messages.warning(request, f"Ad #{pk} '{title[:30]}...' has been deleted.")
        return redirect('/admin/ads/')

class AdminCategoriesView(AdminBaseMixin, View):
    """Catalog Hierarchy Manager (All 12 Main & 76 Subcategories)."""
    def get(self, request):
        parents = (
            Category.objects.filter(parent__isnull=True)
            .prefetch_related('subcategories')
            .annotate(ads_count=Count('ads'))
            .order_by('id')
        )
        catalog_tree = []
        for p in parents:
            subs = []
            for s in p.subcategories.all():
                c = Ads.objects.filter(category=s).count()
                subs.append({
                    "id": s.id,
                    "name": s.category_name,
                    "slug": s.slug,
                    "count": c
                })
            catalog_tree.append({
                "id": p.id,
                "name": p.category_name,
                "slug": p.slug,
                "subcategories": subs,
                "total_count": sum(x['count'] for x in subs)
            })

        context = {
            **self.get_common_context(),
            "active_tab": "categories",
            "catalog_tree": catalog_tree,
            "total_parents": len(catalog_tree),
            "total_subs": sum(len(x['subcategories']) for x in catalog_tree)
        }
        return render(request, "custom_admin/categories.html", context)

class AdminUsersView(AdminBaseMixin, View):
    """Manage Registered Users & Sellers."""
    def get(self, request):
        users = (
            User.objects.annotate(ads_count=Count('author__ads'))
            .order_by('-date_joined')
        )
        context = {
            **self.get_common_context(),
            "active_tab": "users",
            "users": users
        }
        return render(request, "custom_admin/users.html", context)

class AdminAnalyticsView(AdminBaseMixin, View):
    """Full Analytics & Performance Reports."""
    def get(self, request):
        sales_chart = NextAdminManager.get_sales_chart_data()
        inventory = NextAdminManager.get_inventory_overview()
        category_distribution = NextAdminManager.get_category_distribution()
        regional_distribution = NextAdminManager.get_regional_distribution()

        context = {
            **self.get_common_context(),
            "active_tab": "analytics",
            "sales_chart": sales_chart,
            "sales_chart_json": json.dumps(sales_chart),
            "inventory": inventory,
            "category_distribution": category_distribution,
            "regional_distribution": regional_distribution
        }
        return render(request, "custom_admin/analytics.html", context)


class AdminExportDataView(AdminBaseMixin, View):
    """
    Export Center for Administrator:
    Exports Listings (CSV), Users (CSV), and Inventory Trajectory (CSV)
    with full filtering support and UTF-8 Excel compatibility.
    """
    def get(self, request):
        export_type = request.GET.get('type', 'ads').lower()
        now_str = datetime.now().strftime('%Y%m%d_%H%M%S')

        if export_type == 'users':
            return self.export_users(request, now_str)
        elif export_type == 'inventory':
            return self.export_inventory(request, now_str)
        else:
            return self.export_ads(request, now_str)

    def export_ads(self, request, now_str):
        scope = request.GET.get('scope', 'filtered')
        ads_qs = (
            Ads.objects.all()
            .select_related('category', 'category__parent', 'author', 'author__user', 'city', 'state')
            .order_by('-id')
        )

        # Apply active filters unless scope == 'all'
        if scope != 'all':
            query = request.GET.get('q', '').strip()
            cat_id = request.GET.get('category', '')
            user_id = request.GET.get('user', '').strip()
            status = request.GET.get('status', '')

            if user_id:
                ads_qs = ads_qs.filter(author__user_id=user_id)

            if query:
                ads_qs = ads_qs.filter(
                    Q(title__icontains=query) |
                    Q(seller_name__icontains=query) |
                    Q(brand__icontains=query) |
                    Q(city__city_name__icontains=query) |
                    Q(author__user__username__icontains=query) |
                    Q(author__user__first_name__icontains=query) |
                    Q(author__user__last_name__icontains=query) |
                    Q(author__user__email__icontains=query)
                )

            if cat_id:
                ads_qs = ads_qs.filter(Q(category_id=cat_id) | Q(category__parent_id=cat_id))

            if status == 'active':
                ads_qs = ads_qs.filter(is_active=True)
            elif status == 'inactive':
                ads_qs = ads_qs.filter(is_active=False)
            elif status == 'featured':
                ads_qs = ads_qs.filter(is_featured=True)

        filename = f"preloved_listings_{scope}_{now_str}.csv"
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        # UTF-8 BOM so Microsoft Excel renders accented/currency characters seamlessly
        response.write('\ufeff')

        writer = csv.writer(response)
        writer.writerow([
            'Listing ID',
            'Title',
            'Parent Category',
            'Subcategory',
            'Price (INR)',
            'Condition',
            'Brand',
            'Seller Name',
            'Seller Username',
            'Phone',
            'Phone Verified',
            'City',
            'State',
            'Area',
            'Is Active',
            'Is Featured',
            'RC Verified',
            'Registration Number',
            'Negotiable',
            'Seller Type',
            'Date Created',
            'Listing URL'
        ])

        for ad in ads_qs:
            parent_cat = ad.category.parent.category_name if (ad.category and ad.category.parent) else (ad.category.category_name if ad.category else '')
            sub_cat = ad.category.category_name if (ad.category and ad.category.parent) else ''
            seller_username = ad.author.user.username if (ad.author and ad.author.user) else ''
            city_name = ad.city.city_name if ad.city else ''
            state_name = ad.state.state_name if ad.state else ''
            ad_url = f"/ads-details/{ad.id}/"

            writer.writerow([
                ad.id,
                ad.title,
                parent_cat,
                sub_cat,
                float(ad.price) if ad.price else 0.0,
                ad.condition or '',
                ad.brand or '',
                ad.seller_name or '',
                seller_username,
                ad.phone or '',
                'Yes' if ad.is_phone_verified else 'No',
                city_name,
                state_name,
                ad.area or '',
                'Active' if ad.is_active else 'Inactive',
                'Featured' if ad.is_featured else 'Standard',
                'Verified' if ad.is_rc_verified else 'No',
                ad.registration_number or '',
                'Yes' if ad.is_negotiable else 'Fixed',
                ad.seller_type or 'Individual',
                ad.date_created.strftime('%Y-%m-%d %H:%M') if ad.date_created else '',
                ad_url
            ])

        return response

    def export_users(self, request, now_str):
        users = (
            User.objects.annotate(
                ads_count=Count('author__ads'),
                active_ads_count=Count('author__ads', filter=Q(author__ads__is_active=True))
            )
            .select_related('author')
            .order_by('-date_joined')
        )

        filename = f"preloved_users_directory_{now_str}.csv"
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.write('\ufeff')

        writer = csv.writer(response)
        writer.writerow([
            'User ID',
            'Username',
            'First Name',
            'Last Name',
            'Email',
            'Role',
            'Status',
            'Phone',
            'Total Ads Posted',
            'Active Ads',
            'Date Joined',
            'Last Login'
        ])

        for u in users:
            role = 'Super Admin' if u.is_superuser else ('Staff Admin' if u.is_staff else 'Registered Member')
            phone = getattr(u, 'author', None) and getattr(u.author, 'phone', '') or ''
            writer.writerow([
                u.id,
                u.username,
                u.first_name or '',
                u.last_name or '',
                u.email or '',
                role,
                'Active' if u.is_active else 'Disabled',
                phone,
                u.ads_count,
                u.active_ads_count,
                u.date_joined.strftime('%Y-%m-%d %H:%M') if u.date_joined else '',
                u.last_login.strftime('%Y-%m-%d %H:%M') if u.last_login else 'Never'
            ])

        return response

    def export_inventory(self, request, now_str):
        inventory = NextAdminManager.get_inventory_overview()
        cat_dist = NextAdminManager.get_category_distribution()

        filename = f"preloved_inventory_valuation_{now_str}.csv"
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.write('\ufeff')

        writer = csv.writer(response)
        writer.writerow(['PreLoved Marketplace - Inventory & Valuation Report'])
        writer.writerow(['Generated At', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
        writer.writerow(['Total Marketplace Listings', inventory.get('total_listings', 0)])
        writer.writerow(['Active Listings', inventory.get('active_listings', 0)])
        writer.writerow(['Featured Listings', inventory.get('featured_listings', 0)])
        writer.writerow(['RC Verified Vehicles', inventory.get('rc_verified_count', 0)])
        writer.writerow(['Total Cumulative Valuation (INR)', f"{inventory.get('total_valuation_crores', 0)} Crores"])
        writer.writerow([])
        writer.writerow(['Category Breakdown'])
        writer.writerow(['Category Name', 'Total Ads', 'Market Share (%)', 'Gross Valuation (INR)'])

        for c in cat_dist:
            writer.writerow([
                c.get('name', ''),
                c.get('count', 0),
                f"{c.get('percentage', 0)}%",
                c.get('valuation', 0)
            ])

        return response
