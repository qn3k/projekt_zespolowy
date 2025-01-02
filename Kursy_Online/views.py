from django.contrib.auth import login, logout, authenticate
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.conf import settings
from django.utils.crypto import get_random_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.db.models import Max
from django.db import models, transaction
from .code_execution import CodeExecutionService
from .models import User, VerificationCode, LoginHistory, Course, Chapter, Page, UserProgress, ContentPage, \
    CodingExercise
from .serializers import UserRegistrationSerializer, UserSerializer, CourseSerializer, ChapterSerializer, \
    PageSerializer, ContentPageSerializer, QuizSerializer, CodingExerciseSerializer, CodeSubmissionSerializer, \
    TestResultsSerializer, TestCaseSerializer, ContentVideoSerializer, ContentImageSerializer, QuizQuestionSerializer, \
    ContentImageCreateSerializer, ContentVideoCreateSerializer
from django.core.mail import EmailMessage
class AuthViewSet(viewsets.ViewSet):
    def get_permissions(self):
        if self.action in ['register', 'login', 'request_password_reset', 'reset_password_confirm']:
            return [AllowAny()]
        return [IsAuthenticated()]

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

        if not user:
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

        login(request, user)

        LoginHistory.objects.create(
            user=user,
            ip_address=request.META.get('REMOTE_ADDR'),
            device_info=request.META.get('HTTP_USER_AGENT', ''),
            successful=True
        )

        return Response({ 'message': 'Login successful',  'user': UserSerializer(user).data  })

    @action(detail=False, methods=['post'])
    def logout(self, request):
        logout(request)
        return Response({'message': 'Logged out successfully'})

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


class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Course.objects.all()

    @action(detail=True, methods=['post'])
    def add_chapter(self, request, pk=None):
        course = self.get_object()
        serializer = ChapterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(course=course)
            return Response(serializer.data)
        return Response(serializer.errors, status=400)


@action(detail=True, methods=['GET'])
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
    })
class ChapterViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.all()
    serializer_class = ChapterSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        course_id = self.kwargs.get('course_pk')
        return Chapter.objects.filter(course_id=course_id)


class PageViewSet(viewsets.ModelViewSet):
    serializer_class = PageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Page.objects.filter(chapter_id=self.kwargs.get('chapter_pk'))

    def perform_create(self, serializer):
        chapter = Chapter.objects.get(id=self.kwargs.get('chapter_pk'))
        max_order = Page.objects.filter(chapter=chapter).aggregate(Max('order'))['order__max']
        next_order = 1 if max_order is None else max_order + 1
        page = serializer.save(chapter=chapter, order=next_order)
        if page.type == 'CONTENT':
            ContentPage.objects.create(page=page, content="")

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
        if page.type == 'CONTENT':
            serializer = ContentPageSerializer(page.content_page, data=request.data)
        elif page.type == 'QUIZ':
            serializer = QuizSerializer(page.quiz, data=request.data)
        elif page.type == 'CODING':
            serializer = CodingExerciseSerializer(page.coding_exercise, data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    @action(detail=True, methods=['post'])
    def submit_solution(self, request, course_pk=None, chapter_pk=None, pk=None):
        page = self.get_object()

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

        results_serializer = TestResultsSerializer(results)
        return Response(results_serializer.data)
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

        return Response({'message': 'Email verified successfully'})
    except VerificationCode.DoesNotExist:
        return Response({  'error': 'Invalid or expired verification code' }, status=status.HTTP_400_BAD_REQUEST)


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        print(f"Attempting login: username={username}, password={password}")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('login')
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
        user.is_active = False # Konto nieaktywne
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
    return render(request, 'home.html', {'title': 'Strona Główna'})
def test_view(request):
    return render(request, 'test.html', {'title': 'test'})