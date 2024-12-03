from django.db import models
from django.contrib.auth.models import AbstractUser

# Rozszerzenie modelu użytkownika
class User(AbstractUser):
    email = models.EmailField(unique=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)

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
