"""classifiedads URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
"""
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings 

urlpatterns = [
    # Custom NextAdmin Dashboard routes
    path('admin/', include('custom_admin.urls')),
    # Default Django admin backup
    path('django-admin/', admin.site.urls),
    path('', include('pages.urls')),
    path('', include('ads.urls')),
    path('', include('profiles.urls')),
    path('', include('authentication.urls')),
    path('payments/', include('payments.urls')),
]

# if settings.DEBUG:
#     import debug_toolbar
#     urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
#     urlpatterns = [
#         path('__debug__/', include(debug_toolbar.urls)),
#     ] + urlpatterns
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)