from django.contrib.auth import login, logout, authenticate
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.crypto import get_random_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils import timezone
from django.http import Http404, HttpResponseForbidden
from functools import wraps
from rest_framework import permissions
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from django.db.models import Max,Min, Avg, Count
from django.db import models, transaction
from .code_execution import CodeExecutionService
from .utils import distribute_balance
from .models import User, VerificationCode, LoginHistory, PayoutHistory, Course, Chapter, Page, UserProgress, ContentPage, \
    CodingExercise, CourseReview, Payment, Technology, ContentImage, ContentVideo, Quiz, QuizAnswer, QuizQuestion 
from .serializers import UserRegistrationSerializer, PayoutHistorySerializer, UserSerializer, CourseSerializer, ChapterSerializer, \
    PageSerializer, ContentPageSerializer, QuizSerializer, CodingExerciseSerializer, CodeSubmissionSerializer, \
     TestCaseSerializer,ContentVideoSerializer, ContentImageSerializer, QuizQuestionSerializer, \
    ContentImageCreateSerializer, ContentVideoCreateSerializer, CourseReviewSerializer, PublicCourseSerializer, \
    TechnologySerializer, LoginHistorySerializer, PaymentSerializer
from django.core.mail import EmailMessage
import stripe


class IsInstructor(permissions.BasePermission):
    def has_permission(self, request, view):
        course_id = view.kwargs.get('course_pk')
        if not course_id:
            return True
        try:
            course = Course.objects.get(id=course_id)
            return course.instructor == request.user
        except Course.DoesNotExist:
            return False

    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'course'):
            return obj.course.instructor == request.user
        elif hasattr(obj, 'chapter'):
            return obj.chapter.course.instructor == request.user
        return obj.instructor == request.user


class IsModerator(permissions.BasePermission):
    def has_permission(self, request, view):
        course_id = view.kwargs.get('course_pk')
        if not course_id:
            return True
        try:
            course = Course.objects.get(id=course_id)
            return request.user in course.moderators.all()
        except Course.DoesNotExist:
            return False

    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'course'):
            return request.user in obj.course.moderators.all()
        elif hasattr(obj, 'chapter'):
            return request.user in obj.chapter.course.moderators.all()
        return request.user in obj.moderators.all()


class IsStudent(permissions.BasePermission):
    def has_permission(self, request, view):
        course_id = view.kwargs.get('course_pk')
        if not course_id:
            return True
        return Payment.objects.filter(
            user=request.user,
            course_id=course_id,
            status='ACCEPTED'
        ).exists()

    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'course'):
            course = obj.course
        elif hasattr(obj, 'chapter'):
            course = obj.chapter.course
        else:
            course = obj

        return Payment.objects.filter(
            user=request.user,
            course=course,
            status='ACCEPTED'
        ).exists()

class AuthViewSet(viewsets.ViewSet):
    def get_permissions(self):
        return [AllowAny()]

    @action(detail=False, methods=['post'])
    def register(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = serializer.save()
                user.is_active = False
                user.save()

                code = VerificationCode.objects.create(
                    user=user,
                    code=get_random_string(32),
                    purpose='registration',
                    expires_at=timezone.now() + timezone.timedelta(days=1)
                )

                verification_url = f"{request.build_absolute_uri('/api/verify-email/')}?code={code.code}"
                send_mail( 'Verify your email',f'Click here to verify your email: {verification_url}', settings.EMAIL_HOST_USER,[user.email],fail_silently=False,    )

                return Response({
                    'message': 'Registration successful. Please check your email.'
                }, status=status.HTTP_201_CREATED)
            except Exception as e:
                if 'user' in locals():
                    user.delete()
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def login(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(username=username, password=password)

        LoginHistory.objects.create(
            user=user if user else None,
            ip_address=request.META.get('REMOTE_ADDR'),
            device_info=request.META.get('HTTP_USER_AGENT', ''),
            successful=bool(user)
        )

        if not user:
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

        login(request, user)

        return Response({ 'message': 'Login successful',  'user': UserSerializer(user).data  })

    @action(detail=False, methods=['post'])
    def logout(self, request):
        logout(request)
        return redirect('home')

    @action(detail=False, methods=['get', 'put', 'patch'], permission_classes=[IsAuthenticated])
    def profile(self, request):
        if request.method == 'GET':
            serializer = UserSerializer(request.user)
            return Response(serializer.data)

        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            if 'profile_picture' in request.FILES:
                serializer.save(profile_picture=request.FILES['profile_picture'])
            else:
                serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def change_password(self, request):
        user = request.user
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        if not user.check_password(old_password):
            return Response({'error': 'Invalid old password'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_password(new_password)
            user.set_password(new_password)
            user.last_password_change = timezone.now()
            user.save()
            return Response({'message': 'Password changed successfully'})
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def request_password_reset(self, request):
        email = request.data.get('email')
        try:
            user = User.objects.get(email=email)
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            reset_url = f"{request.build_absolute_uri('/api/auth/reset-password-confirm/')}{uid}/{token}/"
            send_mail(
                'Password Reset',
                f'Click here to reset your password: {reset_url}',
                settings.EMAIL_HOST_USER,
                [email],
                fail_silently=False,
            )
            return Response({'message': 'Password reset email sent'})
        except User.DoesNotExist:
            return Response({'message': 'Password reset email sent if account exists'})

    @action(detail=False, methods=['post'], url_path='reset-password-confirm/(?P<uidb64>[^/.]+)/(?P<token>[^/.]+)')
    def reset_password_confirm(self, request, uidb64=None, token=None):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({'error': 'Invalid reset link'}, status=status.HTTP_400_BAD_REQUEST)

        if default_token_generator.check_token(user, token):
            new_password = request.data.get('new_password')
            try:
                validate_password(new_password)
                user.set_password(new_password)
                user.last_password_change = timezone.now()
                user.save()
                return Response({'message': 'Password has been reset'})
            except ValidationError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'error': 'Invalid reset link'}, status=status.HTTP_400_BAD_REQUEST)

def moderator_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, course_id, *args, **kwargs):
        try:
            course = Course.objects.get(id=course_id)
            if not (request.user == course.instructor or request.user in course.moderators.all()):
                messages.error(request, "Nie masz uprawnień do wykonania tej operacji.")
                return redirect('course_detail', course_id=course_id)
            return view_func(request, course_id, *args, **kwargs)
        except Course.DoesNotExist:
            messages.error(request, "Kurs nie został znaleziony.")
            return redirect('home')
    return _wrapped_view

def profile(self, request):
    serializer = UserSerializer(request.user, context={'request': request})
    return Response(serializer.data)

class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create','my_courses','bought_courses']:
            return [IsAuthenticated()]
        elif self.action in ['update', 'partial_update', 'destroy', 'remove_moderator','add_moderator']:
            return [IsAuthenticated(), IsInstructor()]
        elif self.action in ['add_chapter']:
            return [IsAuthenticated(), IsModerator()]
        elif self.action in ['add_review', 'progress']:
            return [IsAuthenticated(), IsStudent()]
        elif self.action in ['reviews', 'list', 'retrieve','search','filters']:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action in ['retrieve', 'list']:
            if not self.request.user.is_authenticated:
                return PublicCourseSerializer

            if self.kwargs.get('pk'):
                course = Course.objects.get(id=self.kwargs.get('pk'))

                has_access = (
                    course.instructor == self.request.user or 
                    self.request.user in course.moderators.all() or
                    Payment.objects.filter(
                        user=self.request.user,
                        course=course,
                        status='ACCEPTED'
                    ).exists()
                )
                return CourseSerializer if has_access else PublicCourseSerializer
        return CourseSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def perform_create(self, serializer):
        course = serializer.save(instructor=self.request.user)
        
        moderators = self.request.data.getlist('moderators', [])
        for moderator_id in moderators:
            course.moderators.add(moderator_id)
        
        course.moderators.add(self.request.user)
        
        technologies = self.request.data.getlist('technologies', [])
        for tech_id in technologies:
            course.technologies.add(tech_id)

        return course
    
    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        
        technologies = request.data.getlist('technologies', [])
        moderators = request.data.getlist('moderators', [])
        
        is_published = request.data.get('is_published', '') == 'on'
        data['is_published'] = is_published
        
        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            course = serializer.save(instructor=request.user)
            
            for tech_id in technologies:
                try:
                    tech = Technology.objects.get(id=tech_id)
                    course.technologies.add(tech)
                except Technology.DoesNotExist:
                    pass
                    
            for mod_id in moderators:
                try:
                    moderator = User.objects.get(id=mod_id)
                    course.moderators.add(moderator)
                except User.DoesNotExist:
                    pass
                    
            course.moderators.add(request.user)
            
            return Response(
                CourseSerializer(course).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['GET'])
    def search(self, request):
        queryset = self.get_queryset()

        title = request.query_params.get('title', '')
        if title:
            queryset = queryset.filter(title__icontains=title)

        technologies = request.query_params.getlist('technologies', [])
        if technologies:
            queryset = queryset.filter(technologies__name__in=technologies)

        level = request.query_params.get('level')
        if level:
            queryset = queryset.filter(level=level)

        min_price = request.query_params.get('min_price')
        max_price = request.query_params.get('max_price')
        if min_price:
            queryset = queryset.filter(price__gte=min_price)
        if max_price:
            queryset = queryset.filter(price__lte=max_price)

        instructor = request.query_params.get('instructor')
        if instructor:
            queryset = queryset.filter(instructor__username=instructor)

        min_rating = request.query_params.get('min_rating')
        if min_rating:
            queryset = queryset.filter(average_rating__gte=min_rating)

        sort_by = request.query_params.get('sort')
        order = request.query_params.get('order', 'asc')
        valid_sort_fields = ['price', 'average_rating', 'created_at']
        if sort_by in valid_sort_fields:
            if order == 'desc':
                sort_by = f'-{sort_by}'
            queryset = queryset.order_by(sort_by)

        page_size = int(request.query_params.get('page_size', 10))
        page = int(request.query_params.get('page', 1))

        paginator = PageNumberPagination()
        paginator.page_size = min(page_size, 10)

        page_items = paginator.paginate_queryset(queryset, request)

        if request.user.is_authenticated:
            purchased_courses = Payment.objects.filter(
                user=request.user,
                status='ACCEPTED'
            ).values_list('course_id', flat=True)

            serializer = CourseSerializer(page_items, many=True, context={
                'request': request,
                'purchased_courses': purchased_courses
            })
        else:
            serializer = PublicCourseSerializer(page_items, many=True)

        return paginator.get_paginated_response({
            'results': serializer.data,
            'filters': {
                'levels': dict(Course.LEVEL_CHOICES),
                'technologies': list(Technology.objects.values('id', 'name')),
                'price_range': {
                    'min': Course.objects.aggregate(Min('price'))['price__min'],
                    'max': Course.objects.aggregate(Max('price'))['price__max']
                }
            }
        })

    @action(detail=False, methods=['GET'])
    def filters(self, request):
        return Response({
            'levels': dict(Course.LEVEL_CHOICES),
            'technologies': TechnologySerializer(
                Technology.objects.all(),
                many=True
            ).data,
            'price_range': {
                'min': Course.objects.aggregate(Min('price'))['price__min'],
                'max': Course.objects.aggregate(Max('price'))['price__max']
            },
            'instructors': UserSerializer(
                User.objects.filter(courses__isnull=False).distinct(),
                many=True
            ).data
        })

    @action(detail=False, methods=['GET'])
    def bought_courses(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Brak dostępu, zaloguj się'}, status=401)

        purchased_courses = Course.objects.filter(
            payments__user=request.user,
            payments__status='ACCEPTED'
        )

        serializer = CourseSerializer(purchased_courses, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['GET'])
    def my_courses(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Brak dostępu, zaloguj się'}, status=401)

        my_courses = Course.objects.filter(
            models.Q(instructor=request.user) |
            models.Q(moderators=request.user)
        ).distinct()

        serializer = CourseSerializer(my_courses, many=True)
        return Response(serializer.data)
    @action(detail=True, methods=['GET'])
    def check_access(self, request, pk=None):
        course = self.get_object()
        has_access = Payment.objects.filter(
            user=request.user,
            course=course,
            status='ACCEPTED'
        ).exists()

        return Response({
            'has_access': has_access
        })

    @action(detail=True, methods=['POST'])
    def add_moderator(self, request, pk=None):
        course = self.get_object()
        if request.user != course.instructor:
            return Response(
                {'error': 'Tylko instruktor może dodawać moderatorów'},
                status=status.HTTP_403_FORBIDDEN
            )

        moderator_id = request.data.get('user_id')
        try:
            new_moderator = User.objects.get(id=moderator_id)
            if new_moderator in course.moderators.all():
                return Response(
                    {'error': 'Ten użytkownik jest już moderatorem'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            course.moderators.add(new_moderator)
            return Response(
                {'message': f'Użytkownik {new_moderator.username} został dodany jako moderator'},
                status=status.HTTP_200_OK
            )
        except User.DoesNotExist:
            return Response(
                {'error': 'Nie znaleziono użytkownika'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['POST'])
    def remove_moderator(self, request, pk=None):
        course = self.get_object()
        try:
            moderator = User.objects.get(id=request.data.get('user_id'))
            if moderator == course.instructor:
                return Response(
                    {'error': 'Nie można usunąć instruktora z moderatorów'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if moderator not in course.moderators.all():
                return Response(
                    {'error': 'Ten użytkownik nie jest moderatorem'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            course.moderators.remove(moderator)
            return Response(
                {'message': f'Użytkownik {moderator.username} został usunięty z moderatorów'}
            )
        except User.DoesNotExist:
            return Response(
                {'error': 'Nie znaleziono użytkownika'},
                status=status.HTTP_404_NOT_FOUND
            )
    def get_queryset(self):
        queryset = Course.objects.annotate(
            average_rating=Avg('reviews__rating'),
            total_reviews=Count('reviews')
        ).prefetch_related('reviews', 'technologies')
        
        # Jeśli użytkownik nie jest zalogowany, pokazuj tylko opublikowane kursy
        if not self.request.user.is_authenticated:
            return queryset.filter(is_published=True)
            
        # Dla zalogowanych użytkowników:
        # - Instruktorzy i moderatorzy widzą swoje kursy
        # - Pozostali użytkownicy widzą zakupione kursy i opublikowane
        if not (self.request.user.is_staff or self.request.user.is_superuser):
            return queryset.filter(
                models.Q(is_published=True) |
                models.Q(instructor=self.request.user) |
                models.Q(moderators=self.request.user) |
                models.Q(payments__user=self.request.user, payments__status='ACCEPTED')
            ).distinct()
        
        return queryset

    @action(detail=True, methods=['post'])
    def add_chapter(self, request, pk=None):
        course = self.get_object()
        serializer = ChapterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(course=course)
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    @action(detail=True, methods=['POST'])
    def add_review(self, request, pk=None):
        course = self.get_object()

        if CourseReview.objects.filter(course=course, user=request.user).exists():
            return Response({'error': 'Kurs został już przez Ciebie oceniony.'}, status=400)

        review = CourseReview.objects.create(
            course=course,
            user=request.user,
            rating=request.data.get('rating'),
            comment=request.data.get('comment', '')
        )
        serializer = CourseReviewSerializer(review)
        return Response(serializer.data)

    @action(detail=True, methods=['GET'])
    def reviews(self, request, pk=None):
        course = self.get_object()
        reviews = CourseReview.objects.filter(course=course)
        serializer = CourseReviewSerializer(reviews, many=True)
        return Response(serializer.data)
    
    '''@action(detail=True, methods=['GET'])
    def progress(self, request, pk=None):
        course = self.get_object()
        user_progress = UserProgress.objects.filter(
            user=request.user,
            page__chapter__course=course
        ).select_related('page')
        total_pages = Page.objects.filter(chapter__course=course).count()
        completed_pages = user_progress.filter(completed=True).count()
        pages_progress = []
        for progress in user_progress:
            pages_progress.append({
                'page_id': progress.page.id,
                'title': progress.page.title,
                'completed': progress.completed,
                'completed_at': progress.completed_at
            })

        return Response({
            'course_id': course.id,
            'total_pages': total_pages,
            'completed_pages': completed_pages,
            'progress_percentage': (completed_pages / total_pages * 100) if total_pages > 0 else 0,
            'pages_progress': pages_progress
        })'''

class ChapterViewSet(viewsets.ModelViewSet):
    serializer_class = ChapterSerializer

    def get_permissions(self):
        if self.action == 'list' or self.action == 'retrieve':
            return [AllowAny()]
        elif self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsModerator()]
        return [IsAuthenticated()]

    def get_queryset(self):
        course_id = self.kwargs.get('course_pk')
        return Chapter.objects.filter(course_id=course_id)
    
    def perform_create(self, serializer):
        course_id = self.kwargs.get('course_pk')
        course = Course.objects.get(id=course_id)

        if not (self.request.user == course.instructor or self.request.user in course.moderators.all()):
            raise PermissionError("Nie masz uprawnień do dodawania rozdziałów do tego kursu")
            
        serializer.save(course_id=course_id)

class PageViewSet(viewsets.ModelViewSet):
    serializer_class = PageSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        elif self.action in ['create', 'update', 'partial_update', 'destroy',
                             'add_quiz_question', 'add_content_image',
                             'add_content_video', 'add_test_case', 'update_content',
                             'update_order']:
            return [IsAuthenticated(), IsModerator()]
        elif self.action == 'submit_solution':
            return [IsAuthenticated(), IsStudent()]
        return [IsAuthenticated()]

    def get_queryset(self):
        chapter_id = self.kwargs.get('chapter_pk')
        course_id = self.kwargs.get('course_pk')
        try:
            chapter = Chapter.objects.get(id=chapter_id)
            course = chapter.course

            if course.instructor == self.request.user or self.request.user in course.moderators.all():
                return Page.objects.filter(chapter_id=chapter_id)

            if Payment.objects.filter(user=self.request.user, course_id=course_id, status='ACCEPTED').exists():
                return Page.objects.filter(chapter_id=chapter_id)

            return Page.objects.filter(chapter_id=chapter_id).only('id', 'title', 'type', 'order')
        except Chapter.DoesNotExist:
            return Page.objects.none()
    def perform_create(self, serializer):
        chapter = Chapter.objects.get(id=self.kwargs.get('chapter_pk'))
        max_order = Page.objects.filter(chapter=chapter).aggregate(Max('order'))['order__max']
        next_order = 1 if max_order is None else max_order + 1
        serializer.save(chapter=chapter, order=next_order)

    def get_serializer_class(self):
        if self.action == 'add_content_image':
            return ContentImageCreateSerializer
        elif self.action == 'add_content_video':
            return ContentVideoCreateSerializer
        return super().get_serializer_class()

    @action(detail=True, methods=['PATCH'])
    def update_order(self, request, course_pk=None, chapter_pk=None, pk=None):
        page = self.get_object()
        new_order = request.data.get('order')

        if new_order is None:
            return Response({'error': 'Nie podano nowej kolejności'}, status=400)

        try:
            new_order = int(new_order)
        except (TypeError, ValueError):
            return Response({'error': 'Kolejność musi być liczbą'}, status=400)

        with transaction.atomic():
            current_order = page.order
            pages = Page.objects.filter(chapter_id=chapter_pk)
            max_order = pages.aggregate(max_order=models.Max('order'))['max_order'] or 0

            if new_order < 1 or new_order > max_order:
                return Response({'error': f'Kolejność musi być między 1 a {max_order}'}, status=400)

            page.order = max_order + 1
            page.save()

            if new_order > current_order:
                pages.filter(
                    order__gt=current_order,
                    order__lte=new_order
                ).exclude(id=page.id).update(order=models.F('order') - 1)
            else:
                pages.filter(
                    order__lt=current_order,
                    order__gte=new_order
                ).exclude(id=page.id).update(order=models.F('order') + 1)

            page.order = new_order
            page.save()

        return Response({
            'message': f'Zmieniono kolejność z {current_order} na {new_order}',
            'current_order': new_order
        })

    @action(detail=True, methods=['post'])
    def add_quiz_question(self, request, *args, **kwargs):
        page = self.get_object()

        if page.type != 'QUIZ':
            return Response(
                {'error': 'Ta strona nie jest quizem'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not hasattr(page, 'quiz'):
            return Response(
                {'error': 'Quiz nie został jeszcze utworzony dla tej strony'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = QuizQuestionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(quiz=page.quiz)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def add_content_image(self, request, *args, **kwargs):
        page = self.get_object()

        if page.type != 'CONTENT':
            return Response(
                {'error': 'Ta strona nie jest stroną z treścią'},
                status=status.HTTP_400_BAD_REQUEST
            )

        content_page, created = ContentPage.objects.get_or_create(
            page=page,
            defaults={'content': ''}
        )
        serializer = ContentImageCreateSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(content_page=content_page)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


    @action(detail=True, methods=['post'])
    def add_content_video(self, request, *args, **kwargs):
        page = self.get_object()

        if page.type != 'CONTENT':
            return Response(
                {'error': 'Ta strona nie jest stroną z treścią'},
                status=status.HTTP_400_BAD_REQUEST
            )
        content_page, created = ContentPage.objects.get_or_create(
            page=page,
            defaults={'content': ''}
        )

        serializer = ContentVideoSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(content_page=content_page)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def add_test_case(self, request, *args, **kwargs):
        page = self.get_object()
        page.refresh_from_db()

        if page.type != 'CODING':
            return Response(
                {'error': 'Ta strona nie jest zadaniem programistycznym'},
                status=status.HTTP_400_BAD_REQUEST
            )

        coding_exercise = CodingExercise.objects.filter(page=page).first()
        if not coding_exercise:
            return Response(
                {'error': 'Zadanie programistyczne nie zostało jeszcze utworzone'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = TestCaseSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(exercise=coding_exercise)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def update_content(self, request, pk=None):
        page = self.get_object()
        print(f"Updating content for page type: {page.type}")  # Debug log
        print(f"Received data: {request.data}") 
        if page.type == 'CONTENT':
            serializer = ContentPageSerializer(page.content_page, data=request.data)

        if page.type == 'QUIZ':
            try:
                quiz = page.quiz
                print(f"Found quiz: {quiz.id}")
                
                serializer = QuizSerializer(quiz, data=request.data)
                print(f"Created serializer, checking validity...")
                
                if serializer.is_valid():
                    print("Serializer is valid, saving...")
                    serializer.save()
                    print("Save completed successfully")
                    return Response(serializer.data)
                else:
                    print(f"Serializer errors: {serializer.errors}")
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            except Quiz.DoesNotExist:
                print("Quiz not found for this page")
                return Response(
                    {'error': 'Quiz not found for this page'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            except Exception as e:
                print(f"Error processing quiz update: {str(e)}")
                return Response(
                    {'error': str(e)}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

                return Response(
                    {'error': 'Unsupported page type'},
                    status=status.HTTP_400_BAD_REQUEST
                )
    
            except Exception as e:
                print(f"Unexpected error in update_content: {str(e)}")
                return Response(
                    {'error': str(e)}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        elif page.type == 'CODING':
            serializer = CodingExerciseSerializer(page.coding_exercise, data=request.data)
        else:
            return Response({'error':'Błędny typ strony.'}, status=400)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    @action(detail=True, methods=['post'])
    def submit_solution(self, request, course_pk=None, chapter_pk=None, pk=None):
        page = self.get_object()
        chapter = page.chapter
        course = chapter.course
        if page.type != 'CODING':
            return Response(
                {'error': 'Ta strona nie jest zadaniem programistycznym'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            coding_exercise = CodingExercise.objects.get(page=page)
        except CodingExercise.DoesNotExist:
            return Response(
                {'error': 'Zadanie programistyczne nie zostało znalezione'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = CodeSubmissionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user_code = serializer.validated_data['code']
        test_cases = coding_exercise.test_cases.all()

        if not test_cases.exists():
            return Response(
                {'error': 'Brak przypadków testowych dla tego zadania'},
                status=status.HTTP_404_NOT_FOUND
            )

        executor = CodeExecutionService()
        results = executor.run_all_tests(
            user_code,
            [
                {
                    'input_data': test.input_data,
                    'expected_output': test.expected_output,
                    'is_hidden': test.is_hidden
                }
                for test in test_cases
            ]
        )

        if results['success']:
            UserProgress.objects.update_or_create(
                user=request.user,
                page=page,
                defaults={
                    'completed': True,
                    'completed_at': timezone.now()
                }
            )

        return Response(results)

@api_view(['GET'])
def verify_email(request):
    code = request.GET.get('code')
    try:
        verification = VerificationCode.objects.get(
            code=code,
            purpose='registration',
            is_used=False,
            expires_at__gt=timezone.now()
        )

        user = verification.user
        user.email_verified = True
        user.is_active = True
        user.save()

        verification.is_used = True
        verification.save()

        return Response({'message': 'Zweryfikowano adres e-mail.'})
    except VerificationCode.DoesNotExist:
        return Response({  'error': 'Nieprawidłowy kod weryfikacyjny.' }, status=status.HTTP_400_BAD_REQUEST)



class PaymentViewSet(viewsets.ViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.is_staff:
            return Payment.objects.all()
        return Payment.objects.filter(user=self.request.user)
        
    def get_permissions(self):
        if self.action == 'create_payment':
            return [IsAuthenticated()]
        if self.action == 'create_top_up':
            return [IsAuthenticated()]
        return [AllowAny()]
    

    @action(detail=False, methods=['POST'], url_path='create/(?P<course_id>[^/.]+)')
    def create_payment(self, request, course_id=None):
        stripe.api_key = settings.STRIPE_SK
        try:
            course = Course.objects.get(id=course_id)
            method = request.data.get('method', 'PAYPAL')

            if Payment.objects.filter(user=request.user, course=course, status='ACCEPTED').exists():
                return Response({'error': 'Już dokonałeś płatności za ten kurs'}, status=400)

            payment = Payment.objects.filter(user=request.user, course=course, status='PENDING').first()
            
            intent = stripe.PaymentIntent.create(
                amount=int(course.price * 100),
                currency='pln',
                payment_method_types=['card', 'paypal'],
                metadata={'course_id': course.id, 'user_id': request.user.id}
            )

            if payment:
                payment.stripe_payment_id = intent.id
                payment.save()
            else:
                payment = Payment.objects.create(
                    user=request.user,
                    course=course,
                    price=course.price,
                    stripe_payment_id=intent.id,
                    status='PENDING'
                )

            return Response({
                'clientSecret': intent.client_secret,
                'publicKey': settings.STRIPE_PK
            })

        except Course.DoesNotExist:
            return Response({'error': 'Wystąpił błąd ze znalezieniem kursu.'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @api_view(['GET'])
    def confirm_payment(request):
        payment_intent_id = request.GET.get('payment_intent')

        if not payment_intent_id:
            return Response({
                'error': 'Brak identyfikatora płatności',
                'redirect_url': settings.FRONTEND_URL + '/payment-error'
            }, status=status.HTTP_400_BAD_REQUEST)

        stripe.api_key = settings.STRIPE_SK

        try:
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            if payment_intent.status != 'succeeded':
                return Response({
                    'error': 'Płatność nie została zatwierdzona',
                    'redirect_url': settings.FRONTEND_URL + '/payment-error'
                }, status=status.HTTP_400_BAD_REQUEST)
            try:
                payment = Payment.objects.get(stripe_payment_id=payment_intent_id)
            except Payment.DoesNotExist:
                return Response({
                    'error': 'Nie znaleziono płatności',
                    'redirect_url': settings.FRONTEND_URL + '/payment-error'
                }, status=status.HTTP_404_NOT_FOUND)

            payment.status = 'ACCEPTED'
            payment.save()

            result = distribute_balance(payment.course, payment.price)

            return Response({
                'message': 'Płatność została potwierdzona',
                'course_id': payment.course.id,
                'redirect_url': f'{settings.FRONTEND_URL}/courses/{payment.course.id}',
                'instructor_balance': result['instructor_balance'],
                'admin_balance': result['admin_balance']
            })

        except stripe.error.StripeError as e:
            return Response({
                'error': str(e),
                'redirect_url': settings.FRONTEND_URL + '/payment-error'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'error': 'Nieznany błąd podczas potwierdzania płatności',
                'redirect_url': settings.FRONTEND_URL + '/payment-error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['POST'], url_path='create-top-up')
    def create_top_up(self, request):
        try:
            amount = float(request.data.get('amount', 0))
            
            if amount < 10 or amount > 1000:
                raise ValueError("Amount must be between 10 and 1000 PLN")
                
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  
                currency='pln',
                payment_method_types=['card'],
                metadata={'user_id': request.user.id, 'type': 'top_up'}
            )
            
            return Response({
                'clientSecret': intent.client_secret
            })
        except (ValueError, TypeError) as e:
            return Response({
                'error': str(e)
            }, status=400)
    
    @action(detail=False, methods=['POST'], url_path='confirm-top-up')
    def confirm_top_up(self, request):
        try:
            payment_intent_id = request.data.get('payment_intent_id')
            amount = float(request.data.get('amount', 0))

            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            if payment_intent.status != 'succeeded':
                return Response({'error': 'Payment not successful'}, status=400)
            
            request.user.balance += amount
            request.user.save()

            return Response({
                'message': f'Successfully added {amount} PLN to your account',
                'new_balance': request.user.balance
            })
        except Exception as e:
            return Response({'error': str(e)}, status=400) 

class PayoutHistoryView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        """
        Zwraca historię wypłat zalogowanego użytkownika.
        """
        payouts = PayoutHistory.objects.filter(user=request.user).order_by('-created_at')
        serializer = PayoutHistorySerializer(payouts, many=True)
        return Response(serializer.data)

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        print(f"Attempting login: username={username}, password={password}")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            print(f"Failed login attempt: username={username}, password={password}")
            messages.error(request, 'Invalid username or password')

    return render(request, 'login.html')

def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        if password != confirm_password:
            messages.error(request, 'Hasła nie są identyczne!')
            return render(request, 'register.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Nazwa użytkownika jest już zajęta!')
            return render(request, 'register.html')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email jest już zarejestrowany')
            return render(request, 'register.html')

        user = User.objects.create_user(username=username, email=email, password=password)
        user.is_active = False 
        user.save()

        # WysyĹ‚anie e-maila aktywacyjnego
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        activation_link = f"{request.build_absolute_uri('/activate/')}?uid={uid}&token={token}"
        subject = 'Potwierdz rejestracje konta!'

        message = f"""
                <p>Cześć {username},</p>
                <br>
                <p>Dziękujemy za rejestracje. Naciśnij prosze poniższy link aby aktywować konto:</p>
                <br>
                <p><a href="{activation_link}">Aktywuj</a></p>
                """
        email_message = EmailMessage(
            subject=subject,
            body=message,
            from_email=settings.EMAIL_HOST_USER,
            to=[email],
        )

        email_message.content_subtype = 'html'
        email_message.send()

        messages.success(request, 'Zarejestrowano pomyślnie. Sprawdź swoją pocztę.')
        return redirect('login')

    return render(request, 'register.html')

def activate_view(request):
    uid = request.GET.get('uid')
    token = request.GET.get('token')

    try:
        user_id = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=user_id)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, 'Twoje konto zostało aktywowane')
        return redirect('login')
    else:
        messages.error(request, 'Link wygasł lub jest niepoprawny')
        return redirect('home')
def home_view(request):
    courses = Course.objects.annotate(
        average_rating=Avg('reviews__rating'),
        total_reviews=Count('reviews')
    ).prefetch_related('reviews', 'chapters', 'technologies')
    
    if not request.user.is_authenticated:
        courses = courses.filter(is_published=True)

    sort_by = request.GET.get('sort', 'title')  
    if sort_by == 'date':
        courses = courses.order_by('-created_at')
    elif sort_by == 'rating':
        courses = courses.order_by('-average_rating')
    else:
        courses = courses.order_by('title')

    context = {
        'title': 'Strona Główna',
        'courses': courses,
    }
    
    return render(request, 'home.html', context)


def password_reset_request_view(request):
    if request.method == "POST":
        email = request.POST.get('email')

        if not email:
            messages.error(request, 'Proszę podać adres e-mail.')
            return render(request, 'password_reset_request.html')

        try:
            user = User.objects.get(email=email)

            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            reset_url = f"{request.build_absolute_uri('/reset-password-confirm/')}{uid}/{token}/"

            subject = 'Reset your password'
            message = f"""
                <p>Cześć,</p>
                <p>Poproszono o zresetowanie hasła do Twojego konta.</p>
                <p>Aby zresetować hasło, kliknij w poniższy link:</p>
                <br>
                <p><a href="{reset_url}">Zresetuj hasło</a></p>
                <p>Jeśli nie prosiłeś o zresetowanie hasła, zignoruj tę wiadomość.</p>
            """
            email_message = EmailMessage(
                subject=subject,
                body=message,
                from_email=settings.EMAIL_HOST_USER,
                to=[email],
            )
            email_message.content_subtype = 'html'
            email_message.send()

            messages.success(request, 'Link do resetu hasła został wysłany na Twój adres e-mail.')
        except User.DoesNotExist:
            messages.error(request, 'Nie znaleziono konta z podanym adresem e-mail.')

        return redirect('login')

    return render(request, 'password_reset_request.html')


def password_reset_confirm_view(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')

            if new_password != confirm_password:
                messages.error(request, 'Hasła nie są identyczne!')
                return redirect('password_reset_confirm', uidb64=uidb64, token=token)

            try:
                validate_password(new_password, user)
                user.set_password(new_password)
                user.last_password_change = timezone.now()
                user.save()
                messages.success(request, 'Hasło zostało pomyślnie zresetowane.')
                return redirect('login')
            except ValidationError as e:
                for error in e.messages:
                    messages.error(request, error)
                return redirect('password_reset_confirm', uidb64=uidb64, token=token)
    else:
        messages.error(request, 'Link resetowania hasła jest nieprawidłowy lub wygasł.')
        return redirect('home')

    return render(request, 'password_reset_confirm.html', {'uidb64': uidb64, 'token': token})

@login_required
def create_course(request):
    if not request.user.is_authenticated:
        return redirect('login')
        
    context = {
        'technologies': Technology.objects.all(),
        'available_moderators': User.objects.exclude(id=request.user.id)
    }
    
    return render(request, 'create_course.html', context)

class TechnologyViewSet(viewsets.ModelViewSet):
    queryset = Technology.objects.all().order_by('name')
    serializer_class = TechnologySerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            self.perform_create(serializer)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@login_required
@user_passes_test(lambda u: u.is_staff)
def technology_management_view(request):
    return render(request, 'technology_management.html')    

def course_detail_view(request, course_id):
    return render(request, 'course_detail.html', {
        'course_id': course_id
    })

@login_required
@moderator_required
def create_chapter_view(request, course_id):
    return render(request, 'create_chapter.html')

@login_required
def profile_view(request):
    return render(request, 'profile.html')

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_balance(request):
    try:
        balance = float(request.user.balance)
        return Response({
            'balance': balance
        })
    except (TypeError, ValueError):
        return Response({
            'balance': 0.0
        })
    
@login_required
def add_balance_view(request):
    context = {
        'stripe_publishable_key': settings.STRIPE_PK
    }
    return render(request, 'add_balance.html', context)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_available_moderators(request):
    users = User.objects.exclude(id=request.user.id)
    serializer = UserSerializer(users, many=True)
    return Response(serializer.data)

@login_required
def my_courses_view(request):
    return render(request, 'my_courses.html')

@login_required
def create_chapter_page(request, course_id, chapter_id):
    try:
        chapter = Chapter.objects.select_related('course').prefetch_related('pages').get(
            id=chapter_id, 
            course_id=course_id
        )
        
        course = chapter.course
        has_access = (
            course.instructor == request.user or 
            request.user in course.moderators.all() or
            Payment.objects.filter(
                user=request.user, 
                course=course, 
                status='ACCEPTED'
            ).exists()
        )
        
        if not has_access:
            return HttpResponseForbidden("Nie masz dostępu do tego rozdziału")
            
        return render(request, 'create_chapter_page.html', {
            'course_id': course_id,
            'chapter_id': chapter_id
        })
        
    except Chapter.DoesNotExist:
        raise Http404("Rozdział nie istnieje")

@login_required
def chapter_detail_view(request, course_id, chapter_id):
    try:
        chapter = Chapter.objects.select_related('course').prefetch_related('pages').get(
            id=chapter_id, 
            course_id=course_id
        )
        
        course = chapter.course
        has_access = (
            course.instructor == request.user or 
            request.user in course.moderators.all() or
            Payment.objects.filter(
                user=request.user, 
                course=course, 
                status='ACCEPTED'
            ).exists()
        )
        
        if not has_access:
            return HttpResponseForbidden("Nie masz dostępu do tego rozdziału")
            
        return render(request, 'chapter_detail.html', {
            'course_id': course_id,
            'chapter_id': chapter_id
        })
        
    except Chapter.DoesNotExist:
        raise Http404("Rozdział nie istnieje")
    
@login_required
def edit_chapter_page_view(request, course_id, chapter_id, page_id):
    try:
        page = Page.objects.get(
            id=page_id,
            chapter_id=chapter_id,
            chapter__course_id=course_id
        )
        course = page.chapter.course
        
        if not (course.instructor == request.user or request.user in course.moderators.all()):
            messages.error(request, 'Nie masz uprawnień do edycji tej strony.')
            return redirect('course_detail', course_id=course_id)
            
        if page.type != 'CONTENT':
            messages.error(request, 'Ta strona nie jest stroną z treścią.')
            return redirect('course_detail', course_id=course_id)
            
        return render(request, 'edit_chapter_page.html')
        
    except Page.DoesNotExist:
        messages.error(request, 'Strona nie została znaleziona.')
        return redirect('course_detail', course_id=course_id)

@login_required
def manage_media_view(request, course_id, chapter_id, page_id):
    try:
        page = Page.objects.select_related(
            'chapter', 
            'chapter__course',
            'contentpage'  
        ).get(
            id=page_id,
            chapter_id=chapter_id,
            chapter__course_id=course_id
        )
    except Page.DoesNotExist:
        return redirect('home')

    course = page.chapter.course
    if not (course.instructor == request.user or request.user in course.moderators.all()):
        return redirect('home')

    if page.type != 'CONTENT':
        return redirect('home')

    context = {
        'title': f'Zarządzanie mediami - {page.title}',
        'course_id': course_id,
        'chapter_id': chapter_id,
        'page_id': page_id,
    }
    
    return render(request, 'manage_media.html', context)

def page_detail_view(request, course_id, chapter_id, page_id):
    return render(request, 'page_detail.html')

class ContentImageViewSet(viewsets.ModelViewSet):
    serializer_class = ContentImageSerializer
    
    def get_queryset(self):
        return ContentImage.objects.filter(content_page=self.kwargs['page_pk'])
        
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)
        
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

class ContentVideoViewSet(viewsets.ModelViewSet):
    serializer_class = ContentVideoSerializer
    
    def get_queryset(self):
        return ContentVideo.objects.filter(content_page=self.kwargs['page_pk'])
        
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)
        
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)
    
def quiz_page_detail_view(request, course_id, chapter_id, page_id):
    return render(request, 'quiz.html', {
        'title': 'Quiz',
        'course_id': course_id,
        'chapter_id': chapter_id,
        'page_id': page_id
    })    

def create_quiz_view(request, course_id, chapter_id):
    return render(request, 'create_quiz.html', {
        'title': 'Tworzenie quizu',
        'course_id': course_id,
        'chapter_id': chapter_id
    })

@login_required
def edit_quiz_view(request, course_id, chapter_id, page_id):
    try:
        page = Page.objects.get(
            id=page_id,
            chapter_id=chapter_id,
            chapter__course_id=course_id
        )
        course = page.chapter.course

        if not (course.instructor == request.user or request.user in course.moderators.all()):
            messages.error(request, 'Nie masz uprawnień do edycji tej strony.')
            return redirect('course_detail', course_id=course_id)
        
        if page.type != 'QUIZ':
            messages.error(request, 'Ta strona nie jest quizem.')
            return redirect('chapter_detail', course_id=course_id, chapter_id=chapter_id)
            
        if not hasattr(page, 'quiz'):
            messages.error(request, 'Quiz nie został znaleziony.')
            return redirect('chapter_detail', course_id=course_id, chapter_id=chapter_id)
        
        return render(request, 'edit_quiz.html', {
            'title': f'Edycja quizu - {page.title}',
            'course_id': course_id,
            'chapter_id': chapter_id,
            'page_id': page_id
        })
        
    except Page.DoesNotExist:
        messages.error(request, 'Strona nie została znaleziona.')
        return redirect('course_detail', course_id=course_id)

@action(detail=True, methods=['PUT', 'PATCH'])
def update_quiz(self, request, course_pk=None, chapter_pk=None, pk=None):
    page = self.get_object()
    if page.type != 'QUIZ':
        return Response(
            {'error': 'This page is not a quiz'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        with transaction.atomic():

            page_data = {
                'title': request.data.get('title'),
                'order': request.data.get('order', page.order)
            }
            page_serializer = PageSerializer(page, data=page_data, partial=True)
            if page_serializer.is_valid():
                page_serializer.save()

            quiz_data = request.data.get('quiz', {})
            quiz = page.quiz
            quiz.description = quiz_data.get('description', '')
            quiz.save()

            quiz.questions.all().delete()  
            for q_data in quiz_data.get('questions', []):
                question = QuizQuestion.objects.create(
                    quiz=quiz,
                    question=q_data['question'],
                    order=q_data.get('order', 1)
                )
                for a_data in q_data.get('answers', []):
                    QuizAnswer.objects.create(
                        question=question,
                        answer=a_data['answer'],
                        is_correct=a_data.get('is_correct', False)
                    )

            return Response(PageSerializer(page).data)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )

class QuizViewSet(viewsets.ModelViewSet):
    serializer_class = QuizSerializer

    def perform_create(self, serializer):
        chapter = Chapter.objects.get(id=self.kwargs.get('chapter_pk'))
        quiz_data = self.request.data.get('quiz', {})
        questions_data = quiz_data.pop('questions', [])
        
        page = serializer.save(
            chapter=chapter,
            type='QUIZ'
        )
        
        quiz = Quiz.objects.create(
            page=page,
            description=quiz_data.get('description', '')
        )
        for question_order, question_data in enumerate(questions_data, 1):
            question = QuizQuestion.objects.create(
                quiz=quiz,
                question=question_data['question'],
                order=question_order
            )
            answers_data = question_data.get('answers', [])
            for answer_data in answers_data:
                QuizAnswer.objects.create(
                    question=question,
                    answer=answer_data['answer'],
                    is_correct=answer_data['is_correct']
                )
        
        return page

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsInstructor()]
        return [IsAuthenticated()]
    
@login_required
def payment_view(request, course_id):
    try:
        course = Course.objects.get(id=course_id)
        if Payment.objects.filter(user=request.user, course=course, status='ACCEPTED').exists():
            return redirect('course_detail', course_id=course_id)
        
        context = {
            'course': course,
            'stripe_publishable_key': settings.STRIPE_PK
        }
        return render(request, 'payment.html', context)
    except Course.DoesNotExist:
        raise Http404("Kurs nie istnieje")

class LoginHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.is_superuser:
            # Admin widzi logowania wszystkich użytkowników
            login_history = LoginHistory.objects.all().order_by('-timestamp')
        else:
            # Zwykły użytkownik widzi tylko swoje logowania
            login_history = LoginHistory.objects.filter(user=request.user).order_by('-timestamp')
        serializer = LoginHistorySerializer(login_history, many=True)
        return Response(serializer.data)
    
@login_required
def rating_view(request, course_id):
    try:
        course_purchased = Payment.objects.filter(
            user=request.user, 
            course_id=course_id, 
            status='ACCEPTED'
        ).exists()

        already_reviewed = CourseReview.objects.filter(
            user=request.user, 
            course_id=course_id
        ).exists()

        if not course_purchased:
            messages.error(request, 'Musisz kupić kurs, aby móc go ocenić.')
            return redirect('course_detail', course_id=course_id)

        if already_reviewed:
            messages.error(request, 'Już oceniłeś ten kurs.')
            return redirect('course_detail', course_id=course_id)

        return render(request, 'rating.html', {'course_id': course_id})
    except Course.DoesNotExist:
        raise Http404("Kurs nie istnieje")