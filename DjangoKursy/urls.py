"""
URL configuration for DjangoKursy project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from Kursy_Online.views import AuthViewSet, verify_email, login_view, home_view


router = DefaultRouter()
router.register(r'auth', AuthViewSet, basename='auth')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/verify-email/', verify_email, name='verify_email'),
    path('login/', login_view, name='login'),
    path('', home_view, name='home'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)