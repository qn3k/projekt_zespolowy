from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_nested import routers
from rest_framework.routers import DefaultRouter
from Kursy_Online.views import AuthViewSet, verify_email, login_view, home_view, PayoutHistoryView, register_view, activate_view,\
    CourseViewSet, ChapterViewSet, PageViewSet, password_reset_request_view, password_reset_confirm_view,create_course,technology_management_view, \
    PaymentViewSet, TechnologyViewSet, course_detail_view, create_chapter_view, profile_view, get_balance, get_available_moderators,    \
    my_courses_view, chapter_detail_view, create_chapter_page, manage_media_view, edit_chapter_page_view, page_detail_view, LoginHistoryView, ContentImageViewSet, ContentVideoViewSet, \
    quiz_page_detail_view, create_quiz_view, create_coding_view, payment_view, edit_quiz_view, rating_view, add_balance_view, python_interpreter, run_code, powershell_interpreter, c_interpreter, csharp_interpreter, java_interpreter, \
    js_interpreter, interpreter_view, coding_page_detail_view, edit_coding_view

# Main router
router = DefaultRouter()
router.register(r'auth', AuthViewSet, basename='auth')
router.register(r'courses', CourseViewSet, basename='course')
router.register(r'payments', PaymentViewSet, basename='payments')
router.register(r'technologies', TechnologyViewSet, basename='technology')

# Nested routers
courses_router = routers.NestedDefaultRouter(router, r'courses', lookup='course')
courses_router.register(r'chapters', ChapterViewSet, basename='course-chapters')

chapters_router = routers.NestedDefaultRouter(courses_router, r'chapters', lookup='chapter')
chapters_router.register(r'pages', PageViewSet, basename='chapter-pages')

# Content management nested routers (for images/videos)
pages_router = routers.NestedDefaultRouter(chapters_router, r'pages', lookup='page')
pages_router.register(r'content_images', ContentImageViewSet, basename='page-images')
pages_router.register(r'content_videos', ContentVideoViewSet, basename='page-videos')

# REMOVE THE EXTRA_ACTIONS OVERRIDE - Let DRF handle @action decorators automatically
# PageViewSet.extra_actions = [...] <-- DELETE THIS ENTIRE BLOCK

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # API Routes
    path('api/', include(router.urls)),
    path('api/', include(courses_router.urls)),
    path('api/', include(chapters_router.urls)),
    path('api/', include(pages_router.urls)),  # This includes all PageViewSet actions automatically
    
    # Custom API endpoints
    path('api/verify-email/', verify_email, name='verify_email'),
    path('api/users/', get_available_moderators, name='available-moderators'),
    path('api/payments/confirm/', PaymentViewSet.as_view({'post': 'confirm_payment'}), name='confirm_payment'),
    path('api/auth/balance/', get_balance, name='get-balance'),
    path('api/payout-history/', PayoutHistoryView.as_view(), name='payout-history'),
    path('api/login_history/', LoginHistoryView.as_view(), name='login_history'),
    path('api/payments/create/<int:course_id>/', PaymentViewSet.as_view({'post': 'create_payment'}), name='create-payment'),
    
    # Authentication & User Management
    path('login/', login_view, name='login'),
    path('logout/', AuthViewSet.as_view({'post': 'logout'}), name='auth-logout'),
    path('register/', register_view, name='register'),
    path('activate/', activate_view, name='activate'),
    path('reset-password/', password_reset_request_view, name='request_password_reset'),
    path('reset-password-confirm/<uidb64>/<token>/', password_reset_confirm_view, name='password_reset_confirm'),
    
    # Main Pages
    path('', home_view, name='home_logged'),
    path('home/', home_view, name='home'),
    path('profile/', profile_view, name='profile'),
    path('my-courses/', my_courses_view, name='my_courses'),
    path('add-balance/', add_balance_view, name='add_balance'),
    path('technologies/', technology_management_view, name='technology_management'),
    
    # Course Management
    path('create-course/', create_course, name='create_course'),
    path('courses/<int:course_id>/', course_detail_view, name='course_detail'),
    path('courses/<int:course_id>/payment/', payment_view, name='course_payment'),
    path('courses/<int:course_id>/rating', rating_view, name='rating_view'),
    path('courses/add-chapter/', create_chapter_view, name='create_chapter'),
    path('courses/<int:course_id>/add-chapter/', create_chapter_view, name='create_chapter_with_id'),
    
    # Chapter Management
    path('courses/<int:course_id>/chapters/<int:chapter_id>/', chapter_detail_view, name='chapter_detail'),
    
    # Page Management
    path('courses/<int:course_id>/chapters/<int:chapter_id>/pages/create/content', create_chapter_page, name='create_chapter_page'),
    path('courses/<int:course_id>/chapters/<int:chapter_id>/pages/create/quiz/', create_quiz_view, name='create_quiz'),
    path('courses/<int:course_id>/chapters/<int:chapter_id>/pages/create/coding/', create_coding_view, name='create_coding'),
    path('courses/<int:course_id>/chapters/<int:chapter_id>/pages/<int:page_id>/', page_detail_view, name='page_detail'),
    path('courses/<int:course_id>/chapters/<int:chapter_id>/pages/<int:page_id>/edit/', edit_chapter_page_view, name='edit_chapter_page'),
    path('courses/<int:course_id>/chapters/<int:chapter_id>/pages/<int:page_id>/media/', manage_media_view, name='manage_media'),
    
    # Specific Page Types
    path('courses/<int:course_id>/chapters/<int:chapter_id>/pages/<int:page_id>/quiz', quiz_page_detail_view, name='quiz_page_detail'),
    path('courses/<int:course_id>/chapters/<int:chapter_id>/pages/<int:page_id>/editquiz/', edit_quiz_view, name='edit_quiz_page'),
    path('courses/<int:course_id>/chapters/<int:chapter_id>/pages/<int:page_id>/coding', coding_page_detail_view, name='coding_page_detail'),
    path('courses/<int:course_id>/chapters/<int:chapter_id>/pages/<int:page_id>/editcoding/', edit_coding_view, name='edit_coding'),
    
    # Code Interpreters
    path('interpreter/', interpreter_view, name='interpreter'),
    path('python-interpreter/', python_interpreter, name='python_interpreter'),
    path('powershell-interpreter/', powershell_interpreter, name='powershell_interpreter'),
    path('c-interpreter/', c_interpreter, name='c_interpreter'),
    path('csharp-interpreter/', csharp_interpreter, name='csharp_interpreter'),
    path('java-interpreter/', java_interpreter, name='java_interpreter'),
    path('js-interpreter/', js_interpreter, name='js_interpreter'),
    path('run-code/', run_code, name='run_code'),
    
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)