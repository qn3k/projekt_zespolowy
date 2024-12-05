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
from .models import User, VerificationCode, LoginHistory
from .serializers import UserRegistrationSerializer, UserSerializer

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

@action(detail=False, methods=['post'])
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

def home_view(request):
    return render(request, 'home.html', {'title': 'Strona Główna'})