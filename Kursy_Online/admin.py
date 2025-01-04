from django.contrib import admin
from .models import User, Course,Technology, Chapter, Page, ContentPage, ContentImage, ContentVideo, Quiz, QuizQuestion, QuizAnswer, CodingExercise, TestCase, UserProgress, CourseReview

admin.site.register(User)
admin.site.register(Course)
admin.site.register(Technology)
admin.site.register(Chapter)
admin.site.register(Page)
admin.site.register(ContentPage)
admin.site.register(ContentImage)
admin.site.register(ContentVideo)
admin.site.register(Quiz)
admin.site.register(QuizQuestion)
admin.site.register(QuizAnswer)
admin.site.register(CodingExercise)
admin.site.register(TestCase)
admin.site.register(UserProgress)
admin.site.register(CourseReview)