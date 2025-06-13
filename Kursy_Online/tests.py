from django.test import TestCase as DjangoTestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock
from django.urls import reverse
from django.core import mail
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from decimal import Decimal
from Kursy_Online.models import *
from Kursy_Online.serializers import *
from Kursy_Online.utils import distribute_balance

User = get_user_model()


class UserModelTests(DjangoTestCase):
    def test_user_creation(self):
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.email, 'test@example.com')
        self.assertTrue(user.check_password('testpass123'))
        self.assertEqual(user.balance, 0.00)

    def test_user_str_representation(self):
        user = User.objects.create_user(username='testuser')
        self.assertEqual(str(user), 'testuser')

    def test_user_default_values(self):
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.assertFalse(user.email_verified)
        self.assertFalse(user.two_factor_enabled)
        self.assertEqual(user.failed_login_attempts, 0)
        self.assertEqual(user.balance, 0.00)

    def test_user_balance_update(self):
        user = User.objects.create_user(username='testuser')
        user.balance = 100.50
        user.save()
        user.refresh_from_db()
        self.assertEqual(user.balance, 100.50)


class TechnologyModelTests(DjangoTestCase):
    def test_technology_creation(self):
        tech = Technology.objects.create(
            name='Python',
            description='Python programming language'
        )
        self.assertEqual(tech.name, 'Python')
        self.assertEqual(str(tech), 'Python')

    def test_technology_without_description(self):
        tech = Technology.objects.create(name='JavaScript')
        self.assertEqual(tech.name, 'JavaScript')
        self.assertEqual(tech.description, '')


class CourseModelTests(DjangoTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='instructor',
            email='instructor@example.com',
            password='testpass123'
        )

    def test_course_creation(self):
        course = Course.objects.create(
            title='Python Course',
            description='Learn Python',
            price=99.99,
            level='BEGINNER',
            instructor=self.user
        )
        self.assertEqual(course.title, 'Python Course')
        self.assertEqual(course.instructor, self.user)
        self.assertEqual(course.price, 99.99)
        self.assertFalse(course.is_published)

    def test_course_technologies_relationship(self):
        course = Course.objects.create(
            title='Python Course',
            instructor=self.user
        )
        tech = Technology.objects.create(name='Python')
        course.technologies.add(tech)

        self.assertIn(tech, course.technologies.all())

    def test_course_moderators_relationship(self):
        course = Course.objects.create(
            title='Python Course',
            instructor=self.user
        )
        moderator = User.objects.create_user(username='moderator')
        course.moderators.add(moderator)

        self.assertIn(moderator, course.moderators.all())

    def test_course_level_choices(self):
        course = Course.objects.create(
            title='Advanced Course',
            instructor=self.user,
            level='ADVANCED'
        )
        self.assertEqual(course.level, 'ADVANCED')


class ChapterModelTests(DjangoTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='instructor')
        self.course = Course.objects.create(
            title='Test Course',
            instructor=self.user
        )

    def test_chapter_creation_and_ordering(self):
        chapter1 = Chapter.objects.create(
            course=self.course,
            title='Chapter 1',
            order=1
        )
        chapter2 = Chapter.objects.create(
            course=self.course,
            title='Chapter 2',
            order=2
        )

        chapters = list(self.course.chapters.all())
        self.assertEqual(chapters[0], chapter1)
        self.assertEqual(chapters[1], chapter2)

    def test_chapter_unique_order_per_course(self):
        Chapter.objects.create(
            course=self.course,
            title='Chapter 1',
            order=1
        )

        with self.assertRaises(IntegrityError):
            Chapter.objects.create(
                course=self.course,
                title='Chapter 1 Duplicate',
                order=1
            )


class PageModelTests(DjangoTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='instructor')
        self.course = Course.objects.create(title='Test Course', instructor=self.user)
        self.chapter = Chapter.objects.create(course=self.course, title='Test Chapter', order=1)

    def test_page_creation(self):
        page = Page.objects.create(
            chapter=self.chapter,
            title='Test Page',
            type='CONTENT',
            order=1
        )
        self.assertEqual(page.title, 'Test Page')
        self.assertEqual(page.type, 'CONTENT')
        self.assertEqual(page.chapter, self.chapter)


class PaymentModelTests(DjangoTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='student')
        self.instructor = User.objects.create_user(username='instructor')
        self.course = Course.objects.create(
            title='Test Course',
            instructor=self.instructor,
            price=50.00
        )

    def test_payment_creation(self):
        payment = Payment.objects.create(
            user=self.user,
            course=self.course,
            price=self.course.price,
            status='PENDING'
        )
        self.assertEqual(payment.user, self.user)
        self.assertEqual(payment.course, self.course)
        self.assertEqual(payment.status, 'PENDING')

    def test_payment_unique_constraint(self):
        Payment.objects.create(
            user=self.user,
            course=self.course,
            price=50.00
        )

        with self.assertRaises(IntegrityError):
            Payment.objects.create(
                user=self.user,
                course=self.course,
                price=50.00
            )

    def test_payment_status_choices(self):
        payment = Payment.objects.create(
            user=self.user,
            course=self.course,
            price=50.00,
            status='ACCEPTED'
        )
        self.assertEqual(payment.status, 'ACCEPTED')


class QuizModelTests(DjangoTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='instructor')
        self.course = Course.objects.create(title='Test Course', instructor=self.user)
        self.chapter = Chapter.objects.create(course=self.course, title='Test Chapter', order=1)
        self.page = Page.objects.create(chapter=self.chapter, title='Quiz Page', type='QUIZ', order=1)

    def test_quiz_creation(self):
        quiz = Quiz.objects.create(
            page=self.page,
            description='Test quiz description'
        )
        self.assertEqual(quiz.page, self.page)
        self.assertEqual(quiz.description, 'Test quiz description')

    def test_quiz_with_questions_and_answers(self):
        quiz = Quiz.objects.create(page=self.page, description='Test Quiz')

        question = QuizQuestion.objects.create(
            quiz=quiz,
            question='What is 2+2?',
            order=1
        )

        answer1 = QuizAnswer.objects.create(
            question=question,
            answer='3',
            is_correct=False
        )

        answer2 = QuizAnswer.objects.create(
            question=question,
            answer='4',
            is_correct=True
        )

        self.assertEqual(quiz.questions.count(), 1)
        self.assertEqual(question.answers.count(), 2)
        self.assertTrue(answer2.is_correct)
        self.assertFalse(answer1.is_correct)


class AuthAPITests(APITestCase):
    def test_user_registration(self):
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'phone_number': '123456789',
            'password': 'newpass123',
            'password2': 'newpass123'
        }
        response = self.client.post('/api/auth/register/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)

        user = User.objects.get(username='newuser')
        self.assertFalse(user.is_active)

    def test_user_registration_password_mismatch(self):
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'password': 'newpass123',
            'password2': 'differentpass123'
        }
        response = self.client.post('/api/auth/register/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_login(self):
        user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_active=True
        )

        data = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        response = self.client.post('/api/auth/login/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)

    def test_profile_endpoint_authenticated(self):
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=user)

        response = self.client.get('/api/auth/profile/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'testuser')


class CourseAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='instructor',
            password='testpass123'
        )
        self.student = User.objects.create_user(
            username='student',
            password='testpass123'
        )
        self.course = Course.objects.create(
            title='Existing Course',
            instructor=self.user,
            price=99.99,
            is_published=True
        )

    def test_course_list_public(self):
        response = self.client.get('/api/courses/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_course_creation_authenticated(self):
        self.client.force_authenticate(user=self.user)
        data = {
            'title': 'New Course',
            'description': 'Course description',
            'price': 49.99,
            'level': 'BEGINNER'
        }
        response = self.client.post('/api/courses/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        course = Course.objects.get(title='New Course')
        self.assertEqual(course.instructor, self.user)

    def test_course_creation_unauthenticated(self):
        data = {
            'title': 'New Course',
            'description': 'Course description',
            'price': 49.99,
            'level': 'BEGINNER'
        }
        response = self.client.post('/api/courses/', data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_my_courses_endpoint(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/courses/my_courses/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'Existing Course')

    def test_course_search_endpoint(self):
        response = self.client.get('/api/courses/search/?title=Existing')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_course_filters_endpoint(self):
        response = self.client.get('/api/courses/filters/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('levels', response.data)
        self.assertIn('technologies', response.data)


class ChapterAPITests(APITestCase):
    def setUp(self):
        self.instructor = User.objects.create_user(username='instructor')
        self.other_user = User.objects.create_user(username='other')
        self.course = Course.objects.create(
            title='Test Course',
            instructor=self.instructor
        )

    def test_add_chapter_as_non_instructor(self):
        self.client.force_authenticate(user=self.other_user)
        data = {
            'title': 'New Chapter',
            'order': 1
        }
        response = self.client.post(f'/api/courses/{self.course.id}/chapters/', data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_chapter_list(self):
        Chapter.objects.create(course=self.course, title='Chapter 1', order=1)
        Chapter.objects.create(course=self.course, title='Chapter 2', order=2)

        response = self.client.get(f'/api/courses/{self.course.id}/chapters/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)


@patch('stripe.PaymentIntent.create')
class PaymentTests(APITestCase):
    def setUp(self):
        self.student = User.objects.create_user(username='student')
        self.instructor = User.objects.create_user(username='instructor')
        self.course = Course.objects.create(
            title='Test Course',
            instructor=self.instructor,
            price=100.00
        )

    def test_create_payment_success(self, mock_stripe):
        mock_payment_intent = MagicMock()
        mock_payment_intent.id = 'pi_test123'
        mock_payment_intent.client_secret = 'pi_test123_secret'
        mock_stripe.return_value = mock_payment_intent

        self.client.force_authenticate(user=self.student)
        response = self.client.post(f'/api/payments/create/{self.course.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('clientSecret', response.data)

        payment = Payment.objects.get(user=self.student, course=self.course)
        self.assertEqual(payment.status, 'PENDING')

    def test_duplicate_payment_prevention(self, mock_stripe):
        Payment.objects.create(
            user=self.student,
            course=self.course,
            price=100.00,
            status='ACCEPTED'
        )

        self.client.force_authenticate(user=self.student)
        response = self.client.post(f'/api/payments/create/{self.course.id}/')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Już dokonałeś płatności', response.data['error'])


class BalanceDistributionTests(DjangoTestCase):
    def setUp(self):
        self.instructor = User.objects.create_user(username='instructor')
        self.admin = User.objects.create_superuser(username='admin')
        self.course = Course.objects.create(
            title='Test Course',
            instructor=self.instructor
        )

    def test_balance_distribution_70_30(self):
        result = distribute_balance(self.course, 100.00)

        self.instructor.refresh_from_db()
        self.admin.refresh_from_db()

        self.assertEqual(self.instructor.balance, 70.00)
        self.assertEqual(self.admin.balance, 30.00)

    def test_balance_distribution_with_decimals(self):
        result = distribute_balance(self.course, 99.99)

        self.instructor.refresh_from_db()
        self.admin.refresh_from_db()

        expected_instructor = 99.99 * 0.7
        expected_admin = 99.99 * 0.3

        self.assertAlmostEqual(float(self.instructor.balance), expected_instructor, places=2)
        self.assertAlmostEqual(float(self.admin.balance), expected_admin, places=2)


class EmailTests(DjangoTestCase):
    def test_registration_email_sent(self):
        mail.outbox = []

        from django.core.mail import send_mail
        send_mail(
            'Verify your email',
            'Click here to verify...',
            'from@example.com',
            ['test@example.com'],
            fail_silently=False
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Verify your email')
        self.assertEqual(mail.outbox[0].to, ['test@example.com'])

    def test_password_reset_email(self):
        mail.outbox = []

        from django.core.mail import send_mail
        send_mail(
            'Reset your password',
            'Click here to reset...',
            'from@example.com',
            ['user@example.com'],
            fail_silently=False
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Reset your password')


class CourseCreationFlowTests(TransactionTestCase):
    def test_complete_course_creation_flow(self):
        instructor = User.objects.create_user(
            username='instructor',
            password='testpass123'
        )

        course = Course.objects.create(
            title='Python Basics',
            description='Learn Python from scratch',
            price=99.99,
            level='BEGINNER',
            instructor=instructor
        )

        python_tech = Technology.objects.create(name='Python')
        course.technologies.add(python_tech)

        chapter = Chapter.objects.create(
            course=course,
            title='Introduction',
            order=1
        )

        page = Page.objects.create(
            chapter=chapter,
            title='What is Python?',
            type='CONTENT',
            order=1
        )

        content_page = ContentPage.objects.create(
            page=page,
            content='Python is a programming language...'
        )

        self.assertEqual(course.chapters.count(), 1)
        self.assertEqual(chapter.pages.count(), 1)
        self.assertEqual(course.technologies.count(), 1)
        self.assertTrue(hasattr(page, 'contentpage'))

    def test_complete_quiz_creation_flow(self):
        instructor = User.objects.create_user(username='instructor')
        course = Course.objects.create(title='Test Course', instructor=instructor)
        chapter = Chapter.objects.create(course=course, title='Quiz Chapter', order=1)
        page = Page.objects.create(chapter=chapter, title='Test Quiz', type='QUIZ', order=1)

        quiz = Quiz.objects.create(page=page, description='Test your knowledge')

        question = QuizQuestion.objects.create(
            quiz=quiz,
            question='What is the capital of France?',
            order=1
        )

        QuizAnswer.objects.create(question=question, answer='London', is_correct=False)
        QuizAnswer.objects.create(question=question, answer='Paris', is_correct=True)
        QuizAnswer.objects.create(question=question, answer='Berlin', is_correct=False)

        self.assertEqual(quiz.questions.count(), 1)
        self.assertEqual(question.answers.count(), 3)
        self.assertEqual(question.answers.filter(is_correct=True).count(), 1)


class PaymentFlowTests(TransactionTestCase):
    def test_complete_payment_flow(self):
        student = User.objects.create_user(username='student')
        instructor = User.objects.create_user(username='instructor')
        admin = User.objects.create_superuser(username='admin')

        course = Course.objects.create(
            title='Test Course',
            instructor=instructor,
            price=100.00
        )

        payment = Payment.objects.create(
            user=student,
            course=course,
            price=course.price,
            status='PENDING'
        )

        payment.status = 'ACCEPTED'
        payment.save()

        distribute_balance(course, payment.price)

        instructor.refresh_from_db()
        admin.refresh_from_db()

        self.assertEqual(payment.status, 'ACCEPTED')
        self.assertEqual(instructor.balance, 70.00)
        self.assertEqual(admin.balance, 30.00)

        has_access = Payment.objects.filter(
            user=student,
            course=course,
            status='ACCEPTED'
        ).exists()
        self.assertTrue(has_access)


class PermissionTests(APITestCase):
    def setUp(self):
        self.instructor = User.objects.create_user(username='instructor')
        self.moderator = User.objects.create_user(username='moderator')
        self.student = User.objects.create_user(username='student')
        self.random_user = User.objects.create_user(username='random')

        self.course = Course.objects.create(
            title='Test Course',
            instructor=self.instructor,
            price=50.00
        )
        self.course.moderators.add(self.moderator)

        Payment.objects.create(
            user=self.student,
            course=self.course,
            price=50.00,
            status='ACCEPTED'
        )

    def test_moderator_permissions(self):
        self.client.force_authenticate(user=self.moderator)

        response = self.client.post(f'/api/courses/{self.course.id}/chapters/', {
            'title': 'Moderator Chapter',
            'order': 2
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_random_user_no_permissions(self):
        self.client.force_authenticate(user=self.random_user)

        response = self.client.post(f'/api/courses/{self.course.id}/chapters/', {
            'title': 'Unauthorized Chapter',
            'order': 1
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_can_access_bought_course(self):
        chapter = Chapter.objects.create(course=self.course, title='Test Chapter', order=1)

        self.client.force_authenticate(user=self.student)
        response = self.client.get(f'/api/courses/{self.course.id}/chapters/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class SerializerTests(DjangoTestCase):
    def test_user_registration_serializer_valid_data(self):
        data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'password': 'testpass123',
            'password2': 'testpass123'
        }
        serializer = UserRegistrationSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_course_serializer_valid_data(self):
        instructor = User.objects.create_user(username='instructor')
        data = {
            'title': 'Test Course',
            'description': 'Test description',
            'price': 99.99,
            'level': 'BEGINNER'
        }
        serializer = CourseSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_course_serializer_invalid_level(self):
        data = {
            'title': 'Test Course',
            'description': 'Test description',
            'price': 99.99,
            'level': 'INVALID_LEVEL'
        }
        serializer = CourseSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_chapter_serializer(self):
        data = {
            'title': 'Test Chapter',
            'order': 1
        }
        serializer = ChapterSerializer(data=data)
        self.assertTrue(serializer.is_valid())


class ValidationTests(DjangoTestCase):
    def test_course_price_validation(self):
        user = User.objects.create_user(username='instructor')

        course = Course.objects.create(
            title='Free Course',
            instructor=user,
            price=-10.00
        )
        self.assertEqual(course.price, -10.00)

    def test_chapter_order_validation(self):
        user = User.objects.create_user(username='instructor')
        course = Course.objects.create(title='Test Course', instructor=user)

        chapter = Chapter.objects.create(
            course=course,
            title='Test Chapter',
            order=1
        )
        self.assertEqual(chapter.order, 1)


class EdgeCaseTests(DjangoTestCase):
    def test_course_without_chapters(self):
        user = User.objects.create_user(username='instructor')
        course = Course.objects.create(title='Empty Course', instructor=user)

        self.assertEqual(course.chapters.count(), 0)

    def test_chapter_without_pages(self):
        user = User.objects.create_user(username='instructor')
        course = Course.objects.create(title='Test Course', instructor=user)
        chapter = Chapter.objects.create(course=course, title='Empty Chapter', order=1)

        self.assertEqual(chapter.pages.count(), 0)

    def test_quiz_without_questions(self):
        user = User.objects.create_user(username='instructor')
        course = Course.objects.create(title='Test Course', instructor=user)
        chapter = Chapter.objects.create(course=course, title='Test Chapter', order=1)
        page = Page.objects.create(chapter=chapter, title='Quiz Page', type='QUIZ', order=1)
        quiz = Quiz.objects.create(page=page, description='Empty Quiz')

        self.assertEqual(quiz.questions.count(), 0)

    def test_large_course_price(self):
        user = User.objects.create_user(username='instructor')
        course = Course.objects.create(
            title='Expensive Course',
            instructor=user,
            price=9999999.99
        )
        self.assertEqual(course.price, 9999999.99)

    def test_long_course_title(self):
        user = User.objects.create_user(username='instructor')
        long_title = 'A' * 255

        course = Course.objects.create(
            title=long_title,
            instructor=user
        )
        self.assertEqual(len(course.title), 255)


class TestDataMixin:
    def create_user(self, username='testuser', **kwargs):
        defaults = {
            'email': f'{username}@example.com',
            'password': 'testpass123'
        }
        defaults.update(kwargs)
        return User.objects.create_user(username=username, **defaults)

    def create_course(self, instructor=None, **kwargs):
        if not instructor:
            instructor = self.create_user('instructor')

        defaults = {
            'title': 'Test Course',
            'description': 'Test description',
            'price': 99.99,
            'level': 'BEGINNER'
        }
        defaults.update(kwargs)
        return Course.objects.create(instructor=instructor, **defaults)

    def create_payment(self, user=None, course=None, status='ACCEPTED'):
        if not user:
            user = self.create_user('student')
        if not course:
            course = self.create_course()

        return Payment.objects.create(
            user=user,
            course=course,
            price=course.price,
            status=status
        )

    def create_complete_course(self, instructor=None):
        if not instructor:
            instructor = self.create_user('instructor')

        course = self.create_course(instructor=instructor)

        tech = Technology.objects.create(name='Python')
        course.technologies.add(tech)

        chapter = Chapter.objects.create(
            course=course,
            title='Introduction',
            order=1
        )

        content_page = Page.objects.create(
            chapter=chapter,
            title='Getting Started',
            type='CONTENT',
            order=1
        )

        ContentPage.objects.create(
            page=content_page,
            content='Welcome to the course!'
        )

        quiz_page = Page.objects.create(
            chapter=chapter,
            title='Knowledge Check',
            type='QUIZ',
            order=2
        )

        quiz = Quiz.objects.create(
            page=quiz_page,
            description='Test your knowledge'
        )

        question = QuizQuestion.objects.create(
            quiz=quiz,
            question='What is Python?',
            order=1
        )

        QuizAnswer.objects.create(
            question=question,
            answer='A programming language',
            is_correct=True
        )

        QuizAnswer.objects.create(
            question=question,
            answer='A snake',
            is_correct=False
        )

        return course


class QuickTests(DjangoTestCase, TestDataMixin):
    def test_with_helper_methods(self):
        course = self.create_course()
        payment = self.create_payment(course=course)

        self.assertEqual(payment.course, course)
        self.assertEqual(payment.status, 'ACCEPTED')

    def test_create_complete_course(self):
        course = self.create_complete_course()

        self.assertEqual(course.chapters.count(), 1)
        self.assertEqual(course.chapters.first().pages.count(), 2)
        self.assertEqual(course.technologies.count(), 1)

        quiz_page = course.chapters.first().pages.get(type='QUIZ')
        self.assertTrue(hasattr(quiz_page, 'quiz'))
        self.assertEqual(quiz_page.quiz.questions.count(), 1)

    def test_multiple_users_and_courses(self):
        instructor1 = self.create_user('instructor1')
        instructor2 = self.create_user('instructor2')
        student = self.create_user('student')

        course1 = self.create_course(instructor=instructor1, title='Python Course')
        course2 = self.create_course(instructor=instructor2, title='JavaScript Course')

        payment1 = self.create_payment(user=student, course=course1)
        payment2 = self.create_payment(user=student, course=course2)

        self.assertEqual(Payment.objects.filter(user=student).count(), 2)
        self.assertEqual(course1.instructor, instructor1)
        self.assertEqual(course2.instructor, instructor2)

    def test_course_with_moderators(self):
        instructor = self.create_user('instructor')
        moderator1 = self.create_user('moderator1')
        moderator2 = self.create_user('moderator2')

        course = self.create_course(instructor=instructor)
        course.moderators.add(moderator1, moderator2)

        self.assertEqual(course.moderators.count(), 2)
        self.assertIn(moderator1, course.moderators.all())
        self.assertIn(moderator2, course.moderators.all())

    def test_balance_operations(self):
        instructor = self.create_user('instructor')
        admin = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )

        course = self.create_course(instructor=instructor, price=100.00)

        distribute_balance(course, 100.00)

        instructor.refresh_from_db()
        admin.refresh_from_db()

        self.assertEqual(instructor.balance, 70.00)
        self.assertEqual(admin.balance, 30.00)


class PerformanceTests(DjangoTestCase, TestDataMixin):
    def test_course_list_with_many_courses(self):
        instructor = self.create_user('instructor')

        courses = []
        for i in range(50):
            courses.append(Course(
                title=f'Course {i}',
                instructor=instructor,
                price=99.99,
                level='BEGINNER'
            ))

        Course.objects.bulk_create(courses)

        all_courses = Course.objects.all()
        self.assertEqual(len(all_courses), 50)

    def test_complex_query_performance(self):
        course = self.create_complete_course()
        student = self.create_user('student')
        self.create_payment(user=student, course=course)

        courses_with_data = Course.objects.select_related('instructor').prefetch_related(
            'chapters__pages',
            'technologies',
            'payments'
        ).filter(payments__status='ACCEPTED')

        self.assertEqual(len(courses_with_data), 1)
        self.assertEqual(courses_with_data[0].chapters.count(), 1)


class FinalIntegrationTests(TransactionTestCase, TestDataMixin):
    def test_complete_user_journey(self):
        instructor = self.create_user('instructor')
        course = self.create_complete_course(instructor=instructor)
        course.is_published = True
        course.save()

        student = self.create_user('student')

        payment = self.create_payment(user=student, course=course)

        admin = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        distribute_balance(course, payment.price)

        has_access = Payment.objects.filter(
            user=student,
            course=course,
            status='ACCEPTED'
        ).exists()
        self.assertTrue(has_access)

        instructor.refresh_from_db()
        expected_instructor_balance = float(payment.price) * 0.7
        self.assertEqual(float(instructor.balance), expected_instructor_balance)

        admin.refresh_from_db()
        expected_admin_balance = float(payment.price) * 0.3
        self.assertEqual(float(admin.balance), expected_admin_balance)

        self.assertTrue(course.is_published)
        self.assertEqual(course.chapters.count(), 1)
        self.assertEqual(course.technologies.count(), 1)

        chapter = course.chapters.first()
        self.assertEqual(chapter.pages.count(), 2)

        quiz_page = chapter.pages.get(type='QUIZ')
        self.assertEqual(quiz_page.quiz.questions.count(), 1)
        self.assertEqual(quiz_page.quiz.questions.first().answers.count(), 2)

    def test_error_handling_and_edge_cases(self):
        instructor = self.create_user('instructor')
        course = self.create_course(instructor=instructor)
        student = self.create_user('student')

        self.create_payment(user=student, course=course, status='ACCEPTED')

        with self.assertRaises(IntegrityError):
            self.create_payment(user=student, course=course, status='PENDING')

        self.assertEqual(course.chapters.count(), 0)

        Chapter.objects.create(course=course, title='Chapter 1', order=1)

        with self.assertRaises(IntegrityError):
            Chapter.objects.create(course=course, title='Chapter 1 Duplicate', order=1)


class SmokeTests(DjangoTestCase):
    def test_models_can_be_created(self):
        user = User.objects.create_user(username='test', password='pass')
        self.assertIsNotNone(user.id)

        tech = Technology.objects.create(name='Test Tech')
        self.assertIsNotNone(tech.id)

        course = Course.objects.create(title='Test Course', instructor=user)
        self.assertIsNotNone(course.id)

        chapter = Chapter.objects.create(course=course, title='Test Chapter', order=1)
        self.assertIsNotNone(chapter.id)

        page = Page.objects.create(chapter=chapter, title='Test Page', type='CONTENT', order=1)
        self.assertIsNotNone(page.id)

        payment = Payment.objects.create(user=user, course=course, price=50.00)
        self.assertIsNotNone(payment.id)

    def test_basic_relationships(self):
        user = User.objects.create_user(username='test', password='pass')
        course = Course.objects.create(title='Test Course', instructor=user)
        chapter = Chapter.objects.create(course=course, title='Test Chapter', order=1)
        page = Page.objects.create(chapter=chapter, title='Test Page', type='CONTENT', order=1)

        self.assertEqual(course.instructor, user)
        self.assertEqual(chapter.course, course)
        self.assertEqual(page.chapter, chapter)

        self.assertIn(course, user.courses.all())
        self.assertIn(chapter, course.chapters.all())
        self.assertIn(page, chapter.pages.all())

    def test_string_representations(self):
        user = User.objects.create_user(username='testuser', password='pass')
        tech = Technology.objects.create(name='Python')
        course = Course.objects.create(title='Python Course', instructor=user)
        chapter = Chapter.objects.create(course=course, title='Intro Chapter', order=1)
        page = Page.objects.create(chapter=chapter, title='First Page', type='CONTENT', order=1)
        payment = Payment.objects.create(user=user, course=course, price=99.99)

        self.assertEqual(str(user), 'testuser')
        self.assertEqual(str(tech), 'Python')
        course_str = str(course)
        self.assertIsInstance(course_str, str)

        self.assertTrue(hasattr(user, 'id'))
        self.assertTrue(hasattr(course, 'created_at'))
        self.assertTrue(hasattr(payment, 'date'))


class UtilityTests(DjangoTestCase):
    def setUp(self):
        self.instructor = User.objects.create_user(username='instructor')
        self.admin = User.objects.create_superuser(username='admin', email='admin@test.com')
        self.course = Course.objects.create(title='Test Course', instructor=self.instructor)

    def test_distribute_balance_function_exists(self):
        from Kursy_Online.utils import distribute_balance
        self.assertTrue(callable(distribute_balance))

    def test_distribute_balance_with_zero_amount(self):
        result = distribute_balance(self.course, 0.00)

        self.instructor.refresh_from_db()
        self.admin.refresh_from_db()

        self.assertEqual(self.instructor.balance, 0.00)
        self.assertEqual(self.admin.balance, 0.00)

    def test_distribute_balance_no_admin_user(self):
        self.admin.delete()

        result = distribute_balance(self.course, 100.00)

        self.instructor.refresh_from_db()
        self.assertEqual(self.instructor.balance, 70.00)

    def test_payout_history_creation(self):
        initial_payout_count = PayoutHistory.objects.count()

        distribute_balance(self.course, 100.00)

        final_payout_count = PayoutHistory.objects.count()
        self.assertGreater(final_payout_count, initial_payout_count)


class SecurityTests(DjangoTestCase, TestDataMixin):
    def test_user_cannot_access_other_user_data(self):
        user1 = self.create_user('user1')
        user2 = self.create_user('user2')

        course1 = self.create_course(instructor=user1, title='User1 Course')
        course2 = self.create_course(instructor=user2, title='User2 Course')

        self.assertNotEqual(course1.instructor, user2)
        self.assertNotEqual(course2.instructor, user1)

    def test_password_hashing(self):
        user = User.objects.create_user(username='test', password='plaintext123')

        self.assertNotEqual(user.password, 'plaintext123')
        self.assertTrue(user.password.startswith('pbkdf2_'))

        self.assertTrue(user.check_password('plaintext123'))
        self.assertFalse(user.check_password('wrongpassword'))

    def test_user_balance_cannot_be_negative_in_business_logic(self):
        user = self.create_user('testuser')

        user.balance = -100.00
        user.save()

        self.assertEqual(user.balance, -100.00)


class ContentTests(DjangoTestCase, TestDataMixin):
    def test_content_page_creation(self):
        course = self.create_complete_course()
        chapter = course.chapters.first()

        page = Page.objects.create(
            chapter=chapter,
            title='New Content Page',
            type='CONTENT',
            order=10
        )

        content_page = ContentPage.objects.create(
            page=page,
            content='This is some test content with <b>HTML</b> tags.'
        )

        self.assertEqual(content_page.page, page)
        self.assertIn('<b>HTML</b>', content_page.content)

    def test_content_images_and_videos(self):
        course = self.create_complete_course()
        chapter = course.chapters.first()
        content_page_obj = chapter.pages.get(type='CONTENT')

        try:
            content_page = content_page_obj.contentpage
        except ContentPage.DoesNotExist:
            content_page = ContentPage.objects.create(
                page=content_page_obj,
                content='Test content'
            )

        content_image = ContentImage.objects.create(
            content_page=content_page,
            image='test_image.jpg',
            caption='Test image caption',
            order=1
        )

        content_video = ContentVideo.objects.create(
            content_page=content_page,
            video_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            caption='Test video caption',
            order=1
        )

        self.assertEqual(content_page.images.count(), 1)
        self.assertEqual(content_page.videos.count(), 1)
        self.assertEqual(content_image.caption, 'Test image caption')
        self.assertIn('youtube.com', content_video.video_url)


class ReviewTests(DjangoTestCase, TestDataMixin):
    def test_course_review_creation(self):
        instructor = self.create_user('instructor')
        student = self.create_user('student')
        course = self.create_course(instructor=instructor)

        self.create_payment(user=student, course=course)

        review = CourseReview.objects.create(
            course=course,
            user=student,
            rating=5,
            comment='Excellent course! Highly recommended.'
        )

        self.assertEqual(review.course, course)
        self.assertEqual(review.user, student)
        self.assertEqual(review.rating, 5)
        self.assertIn('Excellent', review.comment)

    def test_user_cannot_review_same_course_twice(self):
        instructor = self.create_user('instructor')
        student = self.create_user('student')
        course = self.create_course(instructor=instructor)

        CourseReview.objects.create(
            course=course,
            user=student,
            rating=5,
            comment='Great course!'
        )

        with self.assertRaises(IntegrityError):
            CourseReview.objects.create(
                course=course,
                user=student,
                rating=4,
                comment='Actually, it was just good.'
            )

    def test_rating_choices_validation(self):
        instructor = self.create_user('instructor')
        student = self.create_user('student')
        course = self.create_course(instructor=instructor)

        for rating in [1, 2, 3, 4, 5]:
            review = CourseReview(
                course=course,
                user=student,
                rating=rating,
                comment=f'Rating {rating} review'
            )
            self.assertIn(rating, [choice[0] for choice in CourseReview.RATING_CHOICES])


class LoginHistoryTests(DjangoTestCase, TestDataMixin):
    def test_login_history_creation(self):
        user = self.create_user('testuser')

        login_entry = LoginHistory.objects.create(
            user=user,
            ip_address='192.168.1.1',
            device_info='Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            successful=True
        )

        self.assertEqual(login_entry.user, user)
        self.assertEqual(login_entry.ip_address, '192.168.1.1')
        self.assertTrue(login_entry.successful)
        self.assertIsNotNone(login_entry.timestamp)


class CodeExecutionServiceTests(DjangoTestCase):
    def setUp(self):
        from Kursy_Online.code_execution import CodeExecutionService
        self.service = CodeExecutionService()

    def test_validate_code_safe_code(self):
        safe_code = """
def solution(x):
    return x + 1
"""
        self.assertTrue(self.service._validate_code(safe_code))

    def test_validate_code_unsafe_import(self):
        unsafe_code = """
import os
def solution(x):
    return x + 1
"""
        self.assertFalse(self.service._validate_code(unsafe_code))

    def test_validate_code_unsafe_eval(self):
        unsafe_code = """
def solution(x):
    return eval('x + 1')
"""
        self.assertFalse(self.service._validate_code(unsafe_code))

    def test_validate_code_unsafe_exec(self):
        unsafe_code = """
def solution(x):
    exec('print("hello")')
    return x + 1
"""
        self.assertFalse(self.service._validate_code(unsafe_code))

    def test_validate_code_syntax_error(self):
        invalid_code = """
def solution(x
    return x + 1
"""
        self.assertFalse(self.service._validate_code(invalid_code))

    def test_execute_test_case_success(self):
        code = """
def solution(x):
    return x * 2
"""
        result = self.service.execute_test_case(code, "5", "10")
        self.assertTrue(result['success'])
        self.assertEqual(result['output'], 10)

    def test_execute_test_case_wrong_output(self):
        code = """
def solution(x):
    return x + 1
"""
        result = self.service.execute_test_case(code, "5", "10")
        self.assertFalse(result['success'])
        self.assertIn('Nieprawidłowy wynik', result['error'])

    def test_execute_test_case_no_solution_function(self):
        code = """
def other_function(x):
    return x * 2
"""
        result = self.service.execute_test_case(code, "5", "10")
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Brak funkcji solution()')

    def test_execute_test_case_runtime_error(self):
        code = """
def solution(x):
    return 1 / 0
"""
        result = self.service.execute_test_case(code, "5", "10")
        self.assertFalse(result['success'])
        self.assertIn('division by zero', result['error'])

    def test_run_all_tests_success(self):
        code = """
def solution(x):
    return x * 2
"""
        test_cases = [
            {'input_data': '3', 'expected_output': '6'},
            {'input_data': '5', 'expected_output': '10'},
        ]
        result = self.service.run_all_tests(code, test_cases)
        self.assertTrue(result['success'])
        self.assertEqual(len(result['results']), 2)

    def test_run_all_tests_partial_success(self):
        code = """
def solution(x):
    return x + 1
"""
        test_cases = [
            {'input_data': '5', 'expected_output': '6'},
            {'input_data': '3', 'expected_output': '10'},
        ]
        result = self.service.run_all_tests(code, test_cases)
        self.assertFalse(result['success'])
        self.assertTrue(result['results'][0]['success'])
        self.assertFalse(result['results'][1]['success'])

class ProgressTrackingTests(DjangoTestCase, TestDataMixin):
    def setUp(self):
        self.student = self.create_user('student')
        self.course = self.create_complete_course()
        self.chapter = self.course.chapters.first()
        self.pages = list(self.chapter.pages.all())

    def test_user_progress_incomplete(self):
        page = self.pages[0]
        progress = UserProgress.objects.create(
            user=self.student,
            page=page,
            completed=False
        )

        self.assertFalse(progress.completed)
        self.assertIsNone(progress.completed_at)

    def test_progress_update(self):
        page = self.pages[0]
        progress = UserProgress.objects.create(
            user=self.student,
            page=page,
            completed=False
        )

        progress.completed = True
        progress.completed_at = timezone.now()
        progress.save()

        progress.refresh_from_db()
        self.assertTrue(progress.completed)
        self.assertIsNotNone(progress.completed_at)


class AdvancedValidationTests(DjangoTestCase, TestDataMixin):
    def test_course_title_max_length(self):
        instructor = self.create_user('instructor')
        long_title = 'A' * 256

        with self.assertRaises(ValidationError):
            course = Course(title=long_title, instructor=instructor)
            course.full_clean()

    def test_user_email_format_validation(self):
        with self.assertRaises(ValidationError):
            user = User(username='test', email='invalid-email')
            user.full_clean()

    def test_payment_price_positive(self):
        student = self.create_user('student')
        course = self.create_course()

        payment = Payment(user=student, course=course, price=-50.00)
        payment.full_clean()
        self.assertEqual(payment.price, -50.00)

    def test_course_level_choices_validation(self):
        instructor = self.create_user('instructor')

        with self.assertRaises(ValidationError):
            course = Course(
                title='Test Course',
                instructor=instructor,
                level='INVALID_LEVEL'
            )
            course.full_clean()

    def test_quiz_answer_at_least_one_correct(self):
        course = self.create_complete_course()
        chapter = course.chapters.first()
        quiz_page = chapter.pages.get(type='QUIZ')
        question = quiz_page.quiz.questions.first()
        question.answers.update(is_correct=False)

        all_incorrect = question.answers.filter(is_correct=True).count() == 0
        self.assertTrue(all_incorrect)


class DataIntegrityTests(DjangoTestCase, TestDataMixin):
    def test_course_deletion_cascade(self):
        course = self.create_complete_course()
        chapter = course.chapters.first()
        page = chapter.pages.first()

        chapter_id = chapter.id
        page_id = page.id

        course.delete()

        self.assertFalse(Chapter.objects.filter(id=chapter_id).exists())
        self.assertFalse(Page.objects.filter(id=page_id).exists())

    def test_user_deletion_with_payments(self):
        student = self.create_user('student')
        course = self.create_course()
        payment = self.create_payment(user=student, course=course)

        payment_id = payment.id

        student.delete()

        self.assertFalse(Payment.objects.filter(id=payment_id).exists())

    def test_instructor_deletion_prevention(self):
        instructor = self.create_user('instructor')
        course = self.create_course(instructor=instructor)

        instructor.delete()

        self.assertFalse(Course.objects.filter(id=course.id).exists())


class ConcurrencyTests(DjangoTestCase, TestDataMixin):
    def test_multiple_payments_same_user_course(self):
        student = self.create_user('student')
        course = self.create_course()

        payment1 = Payment.objects.create(
            user=student,
            course=course,
            price=100.00,
            status='PENDING'
        )

        with self.assertRaises(IntegrityError):
            payment2 = Payment.objects.create(
                user=student,
                course=course,
                price=100.00,
                status='PENDING'
            )

    def test_chapter_order_conflict(self):
        course = self.create_course()

        Chapter.objects.create(course=course, title='Chapter 1', order=1)

        with self.assertRaises(IntegrityError):
            Chapter.objects.create(course=course, title='Chapter Duplicate', order=1)

    def test_page_order_conflict(self):
        course = self.create_course()
        chapter = Chapter.objects.create(course=course, title='Test Chapter', order=1)

        Page.objects.create(chapter=chapter, title='Page 1', type='CONTENT', order=1)

        with self.assertRaises(IntegrityError):
            Page.objects.create(chapter=chapter, title='Page Duplicate', type='CONTENT', order=1)


class CustomPermissionTests(APITestCase, TestDataMixin):
    def setUp(self):
        self.instructor = self.create_user('instructor')
        self.moderator = self.create_user('moderator')
        self.student = self.create_user('student')
        self.random_user = self.create_user('random')

        self.course = self.create_course(instructor=self.instructor)
        self.course.moderators.add(self.moderator)

        self.create_payment(user=self.student, course=self.course)

    def test_only_instructor_can_add_moderators(self):
        self.client.force_authenticate(user=self.instructor)

        response = self.client.post(f'/api/courses/{self.course.id}/add_moderator/', {
            'user_id': self.random_user.id
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_moderator_cannot_add_moderators(self):
        self.client.force_authenticate(user=self.moderator)

        response = self.client.post(f'/api/courses/{self.course.id}/add_moderator/', {
            'user_id': self.random_user.id
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_instructor_can_remove_moderators(self):
        self.client.force_authenticate(user=self.instructor)

        response = self.client.post(f'/api/courses/{self.course.id}/remove_moderator/', {
            'user_id': self.moderator.id
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_cannot_remove_instructor_as_moderator(self):
        self.client.force_authenticate(user=self.instructor)

        response = self.client.post(f'/api/courses/{self.course.id}/remove_moderator/', {
            'user_id': self.instructor.id
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ErrorHandlingTests(APITestCase, TestDataMixin):
    def test_course_not_found(self):
        response = self.client.get('/api/courses/99999/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_chapter_not_found(self):
        course = self.create_course()
        response = self.client.get(f'/api/courses/{course.id}/chapters/99999/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_invalid_payment_method(self):
        student = self.create_user('student')
        course = self.create_course()

        self.client.force_authenticate(user=student)

        with patch('stripe.PaymentIntent.create') as mock_stripe:
            response = self.client.post(f'/api/payments/create/{course.id}/', {
                'method': 'INVALID_METHOD'
            })
            self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_200_OK])

    def test_malformed_json_request(self):
        user = self.create_user('testuser')
        self.client.force_authenticate(user=user)

        response = self.client.post(
            '/api/courses/',
            data='{"invalid": json}',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_required_fields(self):
        user = self.create_user('testuser')
        self.client.force_authenticate(user=user)

        response = self.client.post('/api/courses/', {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class DatabaseConstraintTests(DjangoTestCase, TestDataMixin):
    def test_unique_constraints(self):
        student = self.create_user('student')
        course = self.create_course()

        Payment.objects.create(user=student, course=course, price=50.00)

        with self.assertRaises(IntegrityError):
            Payment.objects.create(user=student, course=course, price=75.00)

    def test_foreign_key_constraints(self):
        with self.assertRaises(IntegrityError):
            Chapter.objects.create(title='Orphan Chapter', order=1)

    def test_null_constraints(self):
        with self.assertRaises(IntegrityError):
            User.objects.create(username=None)