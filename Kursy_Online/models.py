from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
# Rozszerzenie modelu użytkownika
class User(AbstractUser):
    phone_number = models.CharField(max_length=15, default='')
    email_verified = models.BooleanField(default=False)
    last_password_change = models.DateTimeField(default=timezone.now)
    two_factor_enabled = models.BooleanField(default=False)
    failed_login_attempts = models.IntegerField(default=0)
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)
#Historia logowania
class LoginHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_history')
    ip_address = models.GenericIPAddressField()
    timestamp = models.DateTimeField(auto_now_add=True)
    successful = models.BooleanField(default=True)
    device_info = models.TextField()
#Model dla kodu weryfikacyjnego
class VerificationCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
# Model kursu
class Course(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    instructor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='courses')
    is_public = models.BooleanField(default=True)

    def __str__(self):
        return self.title

# Model lekcji
class Lesson(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=255)
    content = models.TextField()

    def __str__(self):
        return f"{self.course.title} - {self.title}"

# Model zapisów użytkowników na kursy
class Enrollment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrollment_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} -> {self.course.title}"
