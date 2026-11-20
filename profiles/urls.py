from django.urls import path

from .import views

urlpatterns = [
    path('dashboard/', views.profile_dashboard, name='dashboard'),
    path('profile-settings/', views.profile_settings, name='profile-settings'),
    path('my-ads/', views.profile_ads, name='profile-ads'),
    path('favorite-ads/', views.profile_favorite_ads, name='profile-favorite-ads'),
    path('call-requests/', views.profile_call_requests, name='profile-call-requests'),
    path('call-requests/<int:pk>/toggle/', views.toggle_call_request_status, name='toggle-call-request'),
    path('profile-close/', views.profile_close, name='profile-close'),
]