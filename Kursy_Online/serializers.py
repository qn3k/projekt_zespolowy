from django.db import transaction
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from .models import LoginHistory, Technology, Course, Chapter, Page, PayoutHistory, ContentPage, ContentImage, ContentVideo, Quiz, QuizQuestion, QuizAnswer, Payment, CodingExercise, TestCase, CourseReview

User = get_user_model()

class UserInformationSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name',
                 'phone_number', 'email_verified', 'two_factor_enabled', 'balance', 'profile_picture')
        read_only_fields = ('id', 'email_verified', 'balance')

    def get_profile_picture(self, obj):
        request = self.context.get('request')
        if obj.profile_picture and hasattr(obj.profile_picture, 'url'):
            return request.build_absolute_uri(obj.profile_picture.url) if request else obj.profile_picture.url
        return request.build_absolute_uri('/media/profile_pictures/pfp.png') if request else '/media/profile_pictures/pfp.png'

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
        fields = ['content', 'images', 'videos']

class PayoutHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PayoutHistory
        fields = ['id', 'amount', 'created_at', 'description']

class QuizAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizAnswer
        fields = ['id', 'answer', 'is_correct']

class QuizQuestionSerializer(serializers.ModelSerializer):
    answers = QuizAnswerSerializer(many=True, required=False)

    class Meta:
        model = QuizQuestion
        fields = ['id', 'question', 'order', 'answers']

class QuizSerializer(serializers.ModelSerializer):
    questions = QuizQuestionSerializer(many=True, required=False)

    class Meta:
        model = Quiz
        fields = ['description', 'questions']

def update(self, instance, validated_data):
        print(f"QuizSerializer.update() called with data: {validated_data}")
        
        try:
            with transaction.atomic():
                instance.description = validated_data.get('description', instance.description)
                instance.save()

                if 'questions' in validated_data:
                    print("Updating questions...")
                    instance.questions.all().delete()
                    
                    for question_data in validated_data['questions']:
                        print(f"Processing question: {question_data}")
                        question = QuizQuestion.objects.create(
                            quiz=instance,
                            question=question_data['question'],
                            order=question_data.get('order', 1)
                        )

                        for answer_data in question_data.get('answers', []):
                            QuizAnswer.objects.create(
                                question=question,
                                answer=answer_data['answer'],
                                is_correct=answer_data.get('is_correct', False)
                            )
                
                return instance
        except Exception as e:
            print(f"Error in QuizSerializer.update(): {str(e)}")
            raise serializers.ValidationError(str(e))

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
    quiz = QuizSerializer(required=False, read_only=True)
    content_page = ContentPageSerializer(required=False, read_only=True)
    coding_exercise = CodingExerciseSerializer(required=False, read_only=True)

    class Meta:
        model = Page
        fields = ['id', 'title', 'type', 'order', 'quiz', 'content_page', 'coding_exercise']

    def create(self, validated_data):
        page_type = validated_data.get('type')
        page = Page.objects.create(**validated_data)
        
        # Create related objects based on page type
        if page_type == 'QUIZ':
            Quiz.objects.create(page=page, description='')
        elif page_type == 'CONTENT':
            ContentPage.objects.create(page=page, content='')
        elif page_type == 'CODING':
            CodingExercise.objects.create(
                page=page,
                description='',
                initial_code='',
                solution=''
            )
        
        return page

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        # Include related data based on page type
        if instance.type == 'QUIZ':
            try:
                quiz = Quiz.objects.get(page=instance)
                representation['quiz'] = QuizSerializer(quiz).data
            except Quiz.DoesNotExist:
                representation['quiz'] = None
                
        elif instance.type == 'CONTENT':
            try:
                content_page = ContentPage.objects.get(page=instance)
                representation['content_page'] = ContentPageSerializer(content_page).data
            except ContentPage.DoesNotExist:
                representation['content_page'] = {'content': ''}
                
        elif instance.type == 'CODING':
            try:
                coding_exercise = CodingExercise.objects.get(page=instance)
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

class QuizSerializer(serializers.ModelSerializer):
    questions = QuizQuestionSerializer(many=True, required=False)

    class Meta:
        model = Quiz
        fields = ['description', 'questions']

    def update(self, instance, validated_data):
        print(f"QuizSerializer.update() called with data: {validated_data}")
        
        try:
            with transaction.atomic():  # Note: using transaction, not Transaction
                instance.description = validated_data.get('description', instance.description)
                instance.save()

                if 'questions' in validated_data:
                    print("Updating questions...")
                    instance.questions.all().delete()
                    
                    for question_data in validated_data['questions']:
                        print(f"Processing question: {question_data}")
                        question = QuizQuestion.objects.create(
                            quiz=instance,
                            question=question_data['question'],
                            order=question_data.get('order', 1)
                        )

                        for answer_data in question_data.get('answers', []):
                            QuizAnswer.objects.create(
                                question=question,
                                answer=answer_data['answer'],
                                is_correct=answer_data.get('is_correct', False)
                            )
                
                return instance
        except Exception as e:
            print(f"Error in QuizSerializer.update(): {str(e)}")
            raise serializers.ValidationError(str(e))
        
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

    def update(self, instance, validated_data):
        print(f"CodingExerciseSerializer.update() called with data: {validated_data}")
        
        try:
            instance.description = validated_data.get('description', instance.description)
            instance.initial_code = validated_data.get('initial_code', instance.initial_code)
            instance.solution = validated_data.get('solution', instance.solution)
            instance.save()

            if 'test_cases' in validated_data:
                print("Updating test cases...")
                
            return instance
        except Exception as e:
            print(f"Error in CodingExerciseSerializer.update(): {str(e)}")
            raise serializers.ValidationError(str(e))        

class CourseSerializer(serializers.ModelSerializer):
    chapters = ChapterSerializer(many=True, required=False)
    technologies = TechnologySerializer(many=True, required=False)
    reviews = CourseReviewSerializer(many=True, read_only=True)
    average_rating = serializers.FloatField(read_only=True)
    total_reviews = serializers.IntegerField(read_only=True)
    instructor = UserInformationSerializer(read_only=True)
    moderators = UserInformationSerializer(many=True, read_only=True)
    has_access = serializers.SerializerMethodField()
    class Meta:
        model = Course
        fields = ['id', 'title', 'description', 'cover_image', 'price', 'level', 'technologies', 'instructor', 'moderators','created_at', 'updated_at', 'is_published', 'chapters', 'reviews', 'average_rating', 'total_reviews',  'has_access']


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
    
    def get_has_access(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        
        if obj.instructor == request.user or request.user in obj.moderators.all():
            return True
            
        return Payment.objects.filter(
            user=request.user,
            course=obj,
            status='ACCEPTED'
        ).exists()
        
class PublicCourseSerializer(serializers.ModelSerializer):
    instructor = UserSerializer()
    chapters = ChapterSerializer(many=True, required=False)
    content = serializers.SerializerMethodField()
    average_rating = serializers.FloatField()
    total_reviews = serializers.IntegerField()

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'description', 'cover_image',
            'price', 'level', 'instructor', 'content',
            'average_rating', 'total_reviews', 'moderators', 'chapters'
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

class LoginHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = LoginHistory
        fields = ['ip_address', 'device_info', 'timestamp', 'successful']
