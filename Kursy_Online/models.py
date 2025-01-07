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

class Technology(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class Course(models.Model):
    LEVEL_CHOICES = [
        ('BEGINNER', 'Beginner'),
        ('INTERMEDIATE', 'Intermediate'),
        ('ADVANCED', 'Advanced')
    ]

    title = models.CharField(max_length=255)
    description = models.TextField()
    cover_image = models.ImageField(upload_to='course_covers/', null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES)
    technologies = models.ManyToManyField(Technology)
    instructor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='courses')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_published = models.BooleanField(default=False)


class CourseReview(models.Model):
    RATING_CHOICES = [
        (1, '1'),
        (2, '2'),
        (3, '3'),
        (4, '4'),
        (5, '5'),
    ]

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=RATING_CHOICES)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['course', 'user']

class Chapter(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='chapters')
    title = models.CharField(max_length=255)
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ['order']
        unique_together = ['course', 'order']


class Page(models.Model):
    PAGE_TYPES = [
        ('CONTENT', 'Content Page'),
        ('QUIZ', 'Quiz'),
        ('CODING', 'Coding Exercise')
    ]

    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='pages')
    title = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=PAGE_TYPES)
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ['order']
        unique_together = ['chapter', 'order']
    def refresh_from_db(self):
        super().refresh_from_db()
        if hasattr(self, '_coding_exercise_cache'):
            delattr(self, '_coding_exercise_cache')

        def get_coding_exercise(self):
            if self.type == 'CODING':
                return CodingExercise.objects.filter(page=self).first()
            return None

class ContentPage(models.Model):
    page = models.OneToOneField(Page, on_delete=models.CASCADE, primary_key=True)
    content = models.TextField()


class ContentImage(models.Model):
    content_page = models.ForeignKey(ContentPage, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='content_images/')
    caption = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField()


class ContentVideo(models.Model):
    content_page = models.ForeignKey(ContentPage, on_delete=models.CASCADE, related_name='videos')
    video_url = models.URLField()
    caption = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField()


class Quiz(models.Model):
    page = models.OneToOneField(Page, on_delete=models.CASCADE, primary_key=True)
    description = models.TextField(blank=True)


class QuizQuestion(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    question = models.TextField()
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ['order']


class QuizAnswer(models.Model):
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE, related_name='answers')
    answer = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)


class CodingExercise(models.Model):
    page = models.OneToOneField(Page, on_delete=models.CASCADE, primary_key=True)
    description = models.TextField()
    initial_code = models.TextField(blank=True)
    solution = models.TextField(blank=True)
    allowed_languages = models.JSONField(default=list)
    memory_limit = models.IntegerField(default=100*1024*1024)
    time_limit = models.IntegerField(default=5000)


class TestCase(models.Model):
    exercise = models.ForeignKey(CodingExercise, on_delete=models.CASCADE, related_name='test_cases')
    input_data = models.TextField()
    expected_output = models.TextField(null=True, blank=True)
    is_hidden = models.BooleanField(default=False)
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ['order']


class UserProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    page = models.ForeignKey(Page, on_delete=models.CASCADE)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_attempt = models.DateTimeField(auto_now=True)
class Payment(models.Model):
    PAYMENT_CHOICES = [
        ('PAYPAL', 'PayPal'),
     # Blik nie działa w wersji testowej
     #  ('BLIK', 'Blik'),
        ('CARD', 'Card')

    ]
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ACCEPTED', 'Accepted'),
        ('REJECTED', 'Rejected')
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='payments')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default='PAYPAL')
    stripe_payment_id = models.CharField(max_length=255, null=True, blank=True)
    class Meta:
        unique_together = ['user', 'course']