from decimal import Decimal
from .models import User

def distribute_balance(course, amount):
    """
    Rozdziela saldo: 70% dla autora kursu, 30% dla administratora.
    """
    try:
        # Upewnij się, że amount jest typu float
        amount = float(amount)

        # Obliczanie udziałów
        instructor_share = amount * 0.7
        admin_share = amount * 0.3

        # Dodanie balansu dla autora kursu
        instructor = course.instructor
        instructor.balance += instructor_share
        instructor.save()

        # Dodanie balansu dla administratora
        admin = User.objects.filter(is_superuser=True).first()  # Pierwszy admin w systemie
        if admin:
            admin.balance += admin_share
            admin.save()

        return {
            "instructor_balance": instructor.balance,
            "admin_balance": admin.balance if admin else 0.0
        }
    except Exception as e:
        raise ValueError(f"Błąd podczas rozdzielania salda: {str(e)}")
