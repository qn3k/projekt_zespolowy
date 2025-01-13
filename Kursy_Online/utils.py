from .models import User, PayoutHistory

def distribute_balance(course, amount):
    """
    Rozdziela saldo: 70% dla autora kursu, 30% dla administratora.
    Dodaje wpisy do historii wypłat.
    """
    try:
        # Upewnij się, że amount jest typu Decimal
        amount = float(amount)

        # Tworzenie stałych
        instructor_share = amount * 0.7
        admin_share = amount * 0.3

        # Dodanie balansu i historii dla autora kursu
        instructor = course.instructor
        instructor.balance += instructor_share
        instructor.save()

        PayoutHistory.objects.create(
            user=instructor,
            amount=instructor_share,
            description=f"Rozliczenie za kurs: {course.title}"
        )

        # Dodanie balansu i historii dla administratora
        admin = User.objects.filter(is_superuser=True).first()  # Pierwszy admin w systemie
        if admin:
            admin.balance += admin_share
            admin.save()

            PayoutHistory.objects.create(
                user=admin,
                amount=admin_share,
                description=f"Rozliczenie za kurs: {course.title}"
            )

        return {
            "instructor_balance": float(instructor.balance),
            "admin_balance": float(admin.balance) if admin else 0.0
        }
    except Exception as e:
        raise ValueError(f"Błąd podczas rozdzielania salda: {str(e)}")
