from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from .models import Course, LoginHistory, Technology, Course, Chapter, Page, PayoutHistory, ContentPage, ContentImage, ContentVideo, Quiz, QuizQuestion, QuizAnswer, Payment, CodingExercise, TestCase, CourseReview

User = get_user_model()

class UserInformationSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name',
                 'phone_number', 'email_verified', 'two_factor_enabled', 'balance')
        read_only_fields = ('id', 'email_verified', 'balance')

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'user', 'course', 'price', 'status', 'date']

class UserRegistrationSerializer(serializers.ModelSerializer):
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ['email', 'username', 'first_name', 'last_name',
                 'phone_number', 'password', 'password2']
        extra_kwargs = {
            'password': {'write_only': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
            'email': {'required': True}
        }

    def validate_username(self, value):
        if not value.isascii():
            raise serializers.ValidationError("Username can only contain ASCII characters.")
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is already registered.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return data

    def create(self, validated_data):
        validated_data.pop('password2', None)
        password = validated_data.pop('password')
        user = User.objects.create(**validated_data)
        user.set_password(password)
        user.save()
        return user
class TechnologySerializer(serializers.ModelSerializer):
    class Meta:
        model = Technology
        fields = ['id', 'name', 'description']

class ContentImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentImage
        fields = ['id', 'image', 'caption', 'order']

class ContentVideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentVideo
        fields = ['id', 'video_url', 'caption', 'order']

class ContentPageSerializer(serializers.ModelSerializer):
    images = ContentImageSerializer(many=True, read_only=True)
    videos = ContentVideoSerializer(many=True, read_only=True)

    class Meta:
        model = ContentPage
        fields = ['page', 'content', 'images', 'videos']
        read_only_fields = ['page']

class QuizAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizAnswer
        fields = ['id', 'question', 'answer', 'is_correct']
        read_only_fields = ['question']

class QuizQuestionSerializer(serializers.ModelSerializer):
    answers = QuizAnswerSerializer(many=True)

    class Meta:
        model = QuizQuestion
        fields = ['id', 'quiz', 'question', 'order', 'answers']
        read_only_fields = ['quiz']

    def create(self, validated_data):
        answers_data = validated_data.pop('answers')
        question = QuizQuestion.objects.create(**validated_data)

        for answer_data in answers_data:
            QuizAnswer.objects.create(question=question, **answer_data)

        return question

class PayoutHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PayoutHistory
        fields = ['id', 'amount', 'created_at', 'description']

class QuizSerializer(serializers.ModelSerializer):
    questions = QuizQuestionSerializer(many=True, required=False)

    class Meta:
        model = Quiz
        fields = ['page', 'description', 'questions']
        read_only_fields = ['page']
class TestCaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestCase
        fields = ['id', 'exercise', 'input_data', 'expected_output', 'is_hidden', 'order']
        read_only_fields = ['exercise']


class CodingExerciseSerializer(serializers.ModelSerializer):
    test_cases = TestCaseSerializer(many=True, required=False)

    class Meta:
        model = CodingExercise
        fields = ['page', 'description', 'initial_code', 'solution', 'test_cases']
        read_only_fields = ['page']

    def create(self, validated_data):
        test_cases_data = validated_data.pop('test_cases', [])
        coding_exercise = CodingExercise.objects.create(**validated_data)

        for test_case in test_cases_data:
            TestCase.objects.create(exercise=coding_exercise, **test_case)

        return coding_exercise

class PageSerializer(serializers.ModelSerializer):
    content_page = ContentPageSerializer(required=False)
    quiz = QuizSerializer(required=False)
    coding_exercise = CodingExerciseSerializer(required=False)

    class Meta:
        model = Page
        fields = ['id', 'title', 'type', 'order', 'content_page', 'quiz', 'coding_exercise']
        read_only_fields = ['order']

    def create(self, validated_data):
        content_page_data = validated_data.pop('content_page', None)
        quiz_data = validated_data.pop('quiz', None)
        coding_exercise_data = validated_data.pop('coding_exercise', None)

        page = Page.objects.create(**validated_data)

        if page.type == 'CONTENT':
            ContentPage.objects.create(
                page=page,
                content=content_page_data.get('content', '') if content_page_data else ''
            )

        if quiz_data and page.type == 'QUIZ':
            Quiz.objects.create(page=page, **quiz_data)
        if coding_exercise_data and page.type == 'CODING':
            test_cases_data = coding_exercise_data.pop('test_cases', [])
            exercise = CodingExercise.objects.create(page=page, **coding_exercise_data)
            for test_case in test_cases_data:
                TestCase.objects.create(exercise=exercise, **test_case)

        return page

    def update(self, instance, validated_data):
        if instance.type == 'CONTENT':
            content_page = ContentPage.objects.filter(page=instance).first()
            if not content_page:
                ContentPage.objects.create(page=instance, content='')
                instance.refresh_from_db()

        return super().update(instance, validated_data)

    def to_representation(self, instance):

        representation = super().to_representation(instance)

        if instance.type == 'CODING':
            try:
                coding_exercise = instance.codingexercise
                representation['coding_exercise'] = CodingExerciseSerializer(coding_exercise).data
            except CodingExercise.DoesNotExist:
                representation['coding_exercise'] = None

        return representation
class ChapterSerializer(serializers.ModelSerializer):
    pages = PageSerializer(many=True, required=False)

    class Meta:
        model = Chapter
        fields = ['id', 'title', 'order', 'pages']

class CourseReviewSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = CourseReview
        fields = ['id', 'course', 'user', 'rating', 'comment', 'created_at']
        read_only_fields = ['course', 'user']

class CourseSerializer(serializers.ModelSerializer):
    chapters = ChapterSerializer(many=True, required=False)
    technologies = TechnologySerializer(many=True, required=False)
    reviews = CourseReviewSerializer(many=True, read_only=True)
    average_rating = serializers.FloatField(read_only=True)
    total_reviews = serializers.IntegerField(read_only=True)
    instructor = UserInformationSerializer(read_only=True)
    moderators = UserInformationSerializer(many=True, read_only=True)
    class Meta:
        model = Course
        fields = ['id', 'title', 'description', 'cover_image', 'price', 'level', 'technologies', 'instructor', 'moderators','created_at', 'updated_at', 'is_published', 'chapters', 'reviews', 'average_rating', 'total_reviews']


    def create(self, validated_data):
        chapters_data = validated_data.pop('chapters', [])
        technologies_data = validated_data.pop('technologies', [])

        course = Course.objects.create(**validated_data)

        for tech_data in technologies_data:
            technology, _ = Technology.objects.get_or_create(**tech_data)
            course.technologies.add(technology)

        for chapter_data in chapters_data:
            chapter_serializer = ChapterSerializer(data=chapter_data)
            if chapter_serializer.is_valid():
                chapter_serializer.save(course=course)

        return course
        
class PublicCourseSerializer(serializers.ModelSerializer):
    instructor = UserSerializer()
    content = serializers.SerializerMethodField()
    average_rating = serializers.FloatField()
    total_reviews = serializers.IntegerField()

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'description', 'cover_image',
            'price', 'level', 'instructor', 'content',
            'average_rating', 'total_reviews', 'moderators'
        ]

    def get_content(self, obj):
        chapters = obj.chapters.all()
        return [{
            'id': chapter.id,
            'title': chapter.title,
            'pages': [{
                'id': page.id,
                'title': page.title,
                'type': page.type
            } for page in chapter.pages.all()]
        } for chapter in chapters]

class ContentImageCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentImage
        fields = ['id', 'content_page', 'image', 'caption', 'order']
        read_only_fields = ['content_page']
class ContentVideoCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentVideo
        fields = ['id', 'content_page', 'video_url', 'caption', 'order']
        read_only_fields = ['content_page']
class CodeSubmissionSerializer(serializers.Serializer):
    code = serializers.CharField(required=True)
    language = serializers.ChoiceField(choices=['python'], required=True)
