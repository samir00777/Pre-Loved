from django.urls import path
from .views import (
    AdminLoginView,
    AdminLogoutView,
    AdminDashboardView,
    AdminAdsListView,
    AdminAdDetailView,
    AdminAdDeleteView,
    AdminAdToggleActiveView,
    AdminAdToggleFeaturedView,
    AdminCategoriesView,
    AdminUsersView,
    AdminAnalyticsView,
    AdminExportDataView
)

app_name = 'custom_admin'

urlpatterns = [
    # Auth (/admin/login/, /admin/logout/)
    path('login/', AdminLoginView.as_view(), name='login'),
    path('logout/', AdminLogoutView.as_view(), name='logout'),

    # Main Dashboard (/admin/)
    path('', AdminDashboardView.as_view(), name='dashboard'),

    # Ads & Listings (/admin/ads/...)
    path('ads/', AdminAdsListView.as_view(), name='ads-list'),
    path('ads/<int:pk>/', AdminAdDetailView.as_view(), name='ad-detail'),
    path('ads/<int:pk>/delete/', AdminAdDeleteView.as_view(), name='ad-delete'),
    path('ads/<int:pk>/toggle-active/', AdminAdToggleActiveView.as_view(), name='ad-toggle-active'),
    path('ads/<int:pk>/toggle-featured/', AdminAdToggleFeaturedView.as_view(), name='ad-toggle-featured'),

    # Categories (/admin/categories/)
    path('categories/', AdminCategoriesView.as_view(), name='categories'),

    # Users & Sellers (/admin/users/)
    path('users/', AdminUsersView.as_view(), name='users'),

    # Analytics (/admin/analytics/)
    path('analytics/', AdminAnalyticsView.as_view(), name='analytics'),

    # Export Center (/admin/export/)
    path('export/', AdminExportDataView.as_view(), name='export'),
]
