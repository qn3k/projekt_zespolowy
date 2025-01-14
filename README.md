# Strona do kursów
## Wprowadzenie

Aplikacja to kompleksowy system zarządzania kursami online, umożliwiający rejestrację użytkowników, przeglądanie kursów, płatności, zarządzanie treścią kursów oraz wiele innych funkcjonalności. Aplikacja została zbudowana z wykorzystaniem frameworka Django, Django REST Framework oraz Stripe.

---

## Wymagania systemowe

1. Python 3.x+
2. Django 4.x+
3. Stripe CLI (do testowania płatności)
4. Serwer e-mail (SMTP) do wysyłki wiadomości e-mail
5. Baza danych SQLite lub inna zgodna z Django ORM

---

## Uruchomienie projektu

1. Sklonuj repozytorium:

   ```bash
   git clone <adres_repozytorium>
   ```

2. Zainstaluj wymagane biblioteki:

   ```bash
   pip install -r requirements.txt
   ```

3. Wykonaj migracje bazy danych:

   ```bash
   python manage.py migrate
   ```

4. Uruchom serwer deweloperski:

   ```bash
   python manage.py runserver
   ```

---

## Technologie użyte w projekcie

1. Django 5.1.4
2. Django REST Framework
3. Stripe API
4. SQLite
5. HTML, CSS, JavaScript (dla widoków)

---

## Struktura projektu

### Główne komponenty aplikacji:

1. **Autoryzacja i uwierzytelnianie**:

   - Rejestracja użytkowników
   - Logowanie/wylogowywanie
   - Resetowanie hasła

2. **Zarządzanie kursami**:

   - Tworzenie kursów, rozdziałów i stron kursu
   - Dodawanie moderatorów i recenzji kursów
   - Filtry i wyszukiwanie kursów

3. **Płatności**:

   - Integracja z Stripe
   - Zarządzanie płatnościami za kursy
   - Historia wypłat instruktora

4. **Treści multimedialne i zadania**:

   - Obsługa treści, quizów, ćwiczeń programistycznych
   - Przypadki testowe dla zadań programistycznych

5. **Role użytkowników**:

   - Instruktorzy
   - Moderatorzy
   - Uczniowie

6. **Widoki dla administratorów i użytkowników**:

   - Widoki HTML dla użytkowników końcowych
   - API REST dla integracji

---

## Opis funkcjonalności

### 1. Autoryzacja i uwierzytelnianie

- **Rejestracja**:

  - Endpoint: `/api/auth/register/`
  - Walidacja danych użytkownika i wysyłka kodu weryfikacyjnego na e-mail.

- **Logowanie**:

  - Endpoint: `/api/auth/login/`
  - Uwierzytelnianie za pomocą nazwy użytkownika i hasła.

- **Resetowanie hasła**:

  - Proces:
    - Wysłanie e-maila z linkiem do resetowania hasła.
    - Walidacja tokenu i zmiana hasła.

- **Profil użytkownika**:

  - Endpoint: `/api/auth/profile/`
  - Pobieranie i edycja danych profilu (np. zdjęcia profilowego).

#### Przykładowy fragment kodu: Rejestracja użytkownika

```python
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
            send_mail(
                'Verify your email',
                f'Click here to verify your email: {verification_url}',
                settings.EMAIL_HOST_USER,
                [user.email],
                fail_silently=False,
            )

            return Response({
                'message': 'Registration successful. Please check your email.'
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            if 'user' in locals():
                user.delete()
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
```

### 2. Zarządzanie kursami

- **Tworzenie kursów**:

  - Endpoint: `/api/courses/`
  - Instruktor może dodać technologie oraz moderatorów do kursu.

- **Dodawanie rozdziałów**:

  - Endpoint: `/api/courses/{course_id}/chapters/`
  - Instruktor lub moderator może dodawać rozdziały do kursu.

#### Przykładowy fragment kodu: Dodawanie rozdziału do kursu

```python
@action(detail=True, methods=['post'])
def add_chapter(self, request, pk=None):
    course = self.get_object()
    serializer = ChapterSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(course=course)
        return Response(serializer.data)
    return Response(serializer.errors, status=400)
```

- **Dodawanie stron do rozdziałów**:

  - Obsługa różnych typów stron (treść, quizy, ćwiczenia programistyczne).

- **Recenzje kursów**:

  - Endpoint: `/api/courses/{course_id}/reviews/`
  - Uczniowie mogą dodawać recenzje do ukończonych kursów.

- **Filtry i wyszukiwanie**:

  - Wyszukiwanie kursów po tytule, technologiach, poziomie trudności, cenie i ocenie.

### 3. Płatności

- **Tworzenie płatności**:

  - Endpoint: `/api/payments/create/{course_id}/`
  - Użytkownicy mogą płacić za kursy poprzez Stripe.

#### Przykładowy fragment kodu: Tworzenie płatności

```python
@action(detail=False, methods=['POST'], url_path='create/(?P<course_id>[^/.]+)')
def create_payment(self, request, course_id=None):
    stripe.api_key = settings.STRIPE_SK
    try:
        course = Course.objects.get(id=course_id)
        method = request.data.get('method', 'PAYPAL')
        if Payment.objects.filter(user=request.user, course=course, status='ACCEPTED').exists():
            return Response({'error': 'Już dokonałeś płatności za ten kurs'}, status=400)
        if method not in ['PAYPAL','CARD']:
            return Response({'error': 'Nie obsługujemy tej metody płatności.'}, status=400)
        id = stripe.PaymentIntent.create(
            amount=int(course.price * 100),
            currency='pln',
            payment_method_types=['card', 'paypal'],
            metadata={'course_id': course.id, 'user_id': request.user.id}
        )
        payment = Payment.objects.create(
            user=request.user,
            course=course,
            price=course.price,
            stripe_payment_id=id.id,
            status='PENDING'
        )

        return Response({
            'clientSecret': id.client_secret,
            'publicKey': settings.STRIPE_PK
        })

    except Course.DoesNotExist:
        return Response({'error': 'Wystąpił błąd ze znalezieniem kursu.'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=400)
```

- **Potwierdzanie płatności**:

  - Endpoint: `/api/payments/confirm/{payment_intent_id}/`
  - Potwierdzanie płatności i rozdzielenie środków między instruktorem a administratorem.

- **Historia wypłat**:

  - Endpoint: `/api/payout-history/`
  - Zwracanie historii wypłat instruktora.

---

## Uwagi końcowe

- Aplikacja jest w pełni skalowalna i może być rozwijana o dodatkowe funkcjonalności.
- W przypadku pytań lub problemów należy skontaktować się z zespołem deweloperskim.

---

Wykonali: Jakub Jankowski, Kamil Konkol , Kacper Miś
