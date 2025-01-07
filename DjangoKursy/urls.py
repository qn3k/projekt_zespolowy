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
from rest_framework_nested import routers
from rest_framework.routers import DefaultRouter
from Kursy_Online.views import AuthViewSet, verify_email, login_view, home_view, register_view, activate_view, \
    CourseViewSet, ChapterViewSet, PageViewSet, test_view, password_reset_request_view, password_reset_confirm_view, \
    PaymentViewSet

router = DefaultRouter()
router.register(r'auth', AuthViewSet, basename='auth')
router.register(r'courses', CourseViewSet)
router.register(r'payments', PaymentViewSet, basename='payments')
courses_router = routers.NestedDefaultRouter(router, r'courses', lookup='course')
courses_router.register(r'chapters', ChapterViewSet, basename='course-chapters')

chapters_router = routers.NestedDefaultRouter(courses_router, r'chapters', lookup='chapter')
chapters_router.register(r'pages', PageViewSet, basename='chapter-pages')

PageViewSet.extra_actions = [
    {'url_path': 'add_quiz_question', 'url_name': 'add-quiz-question'},
    {'url_path': 'add_content_image', 'url_name': 'add-content-image'},
    {'url_path': 'add_content_video', 'url_name': 'add-content-video'},
    {'url_path': 'add_test_case', 'url_name': 'add-test-case'},
    {'url_path': 'update_order', 'url_name': 'update-order'},
]
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/verify-email/', verify_email, name='verify_email'),
    path('api/', include(courses_router.urls)),
    path('api/', include(chapters_router.urls)),
    path('login/', login_view, name='login'),
    path('', home_view, name='home'),
    path('register/', register_view, name='register'),
    path('activate/', activate_view, name='activate'),
    path('reset-password/', password_reset_request_view, name='request_password_reset'),
    path('reset-password-confirm/<uidb64>/<token>/', password_reset_confirm_view, name='password_reset_confirm'),
    path('test/', test_view, name='test'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)