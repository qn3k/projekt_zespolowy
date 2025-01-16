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
from Kursy_Online.views import AuthViewSet, verify_email, login_view, home_view, PayoutHistoryView, register_view, activate_view,\
    CourseViewSet, ChapterViewSet, PageViewSet, password_reset_request_view, password_reset_confirm_view,create_course,technology_management_view, \
    PaymentViewSet, TechnologyViewSet, course_detail_view, create_chapter_view, profile_view, get_balance, get_available_moderators,    \
    my_courses_view, chapter_detail_view, create_chapter_page, manage_media_view, edit_chapter_page_view, page_detail_view, ContentImageViewSet, ContentVideoViewSet, \
    quiz_page_detail_view, create_quiz_view


router = DefaultRouter()
router.register(r'auth', AuthViewSet, basename='auth')
router.register(r'courses', CourseViewSet, basename='course')
router.register(r'payments', PaymentViewSet, basename='payments')
router.register(r'technologies', TechnologyViewSet, basename='technology')
courses_router = routers.NestedDefaultRouter(router, r'courses', lookup='course')
courses_router.register(r'chapters', ChapterViewSet, basename='course-chapters')
chapters_router = routers.NestedDefaultRouter(courses_router, r'chapters', lookup='chapter')
chapters_router.register(r'pages', PageViewSet, basename='chapter-pages')
pages_router = routers.NestedDefaultRouter(chapters_router, r'pages', lookup='page')
pages_router.register(r'content_images', ContentImageViewSet, basename='page-images')
pages_router.register(r'content_videos', ContentVideoViewSet, basename='page-videos')


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
    path('api/', include(router.urls)),
    path('api/', include(pages_router.urls)),
    path('api/users/', get_available_moderators, name='available-moderators'),
    path('login/', login_view, name='login'),
    path('logout/', AuthViewSet.as_view({'post': 'logout'}), name='auth-logout'),
    path('', home_view, name='home'),
    path('register/', register_view, name='register'),
    path('activate/', activate_view, name='activate'),
    path('reset-password/', password_reset_request_view, name='request_password_reset'),
    path('create-course/', create_course, name='create_course'),
    path('courses/<int:course_id>/', course_detail_view, name='course_detail'),
    path('courses/add-chapter/', create_chapter_view, name='create_chapter'),
    path('courses/<int:course_id>/add-chapter/', create_chapter_view, name='create_chapter_with_id'),
    path('courses/<int:course_id>/chapters/<int:chapter_id>/', chapter_detail_view, name='chapter_detail'),
    path('courses/<int:course_id>/chapters/<int:chapter_id>/pages/create/content', create_chapter_page, name='create_chapter_page'),
    path('courses/<int:course_id>/chapters/<int:chapter_id>/pages/<int:page_id>/media/', manage_media_view, name='manage_media'),
    path('courses/<int:course_id>/chapters/<int:chapter_id>/pages/<int:page_id>/edit/', edit_chapter_page_view, name='edit_chapter_page'),
    path('courses/<int:course_id>/chapters/<int:chapter_id>/pages/<int:page_id>/', page_detail_view, name='page_detail'),
    path('courses/<int:course_id>/chapters/<int:chapter_id>/pages/<int:page_id>/quiz', quiz_page_detail_view, name='quiz_page_detail'),
    path('courses/<int:course_id>/chapters/<int:chapter_id>/pages/create/quiz/',create_quiz_view,name='create_quiz'),
    path('profile/', profile_view, name='profile'),
    path('my-courses/', my_courses_view, name='my_courses'),
    path('api/auth/balance/', get_balance, name='get-balance'),
    path('api/payout-history/', PayoutHistoryView.as_view(), name='payout-history'),
    path('technologies/', technology_management_view, name='technology_management'),
    path('reset-password-confirm/<uidb64>/<token>/', password_reset_confirm_view, name='password_reset_confirm')
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)