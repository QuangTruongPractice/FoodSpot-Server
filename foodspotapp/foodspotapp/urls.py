from django.urls import path, include, re_path
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.contrib import admin

urlpatterns = [
    path('', include('foodspots.urls')),
    path('admin/', admin.site.urls),
]