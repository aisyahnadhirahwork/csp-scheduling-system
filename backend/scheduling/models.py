from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.db.models import Q, F
class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)  # hashes the password
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom User model for scheduling system"""
    USER_TYPE_CHOICES = (
        ("patient", "Patient"),
        ("doctor", "Doctor"),
    )

    user_id = models.AutoField(primary_key=True)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # required for admin

    objects = CustomUserManager()

    USERNAME_FIELD = "email"  # login with email
    REQUIRED_FIELDS = ["first_name", "last_name", "user_type"]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"

    class Meta:
        db_table = "users"
class Patient(models.Model):
    """Patients table with patient_id (PK) and user_id (FK)"""
    patient_id = models.AutoField(primary_key=True)
    user_id = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Patient: {self.user_id.first_name} {self.user_id.last_name}"

    class Meta:
        db_table = "patients"


class Doctor(models.Model):
    """Doctors table with doctor_id (PK), user_id (FK), specialisation, and gender"""
    GENDER_CHOICES = (
        ("M", "Male"),
        ("F", "Female"),
    )
    
    doctor_id = models.AutoField(primary_key=True)
    user_id = models.ForeignKey(User, on_delete=models.CASCADE)
    specialisation = models.CharField(max_length=100)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Dr. {self.user_id.first_name} {self.user_id.last_name} - {self.specialisation}"

    class Meta:
        db_table = "doctors"

class DoctorBlockedSlot(models.Model):
    blocked_id = models.AutoField(primary_key=True)

    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.CASCADE,
        related_name='blocked_slots'
    )

    blocked_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    reason = models.CharField(
        max_length=50,
        choices=[
            ('unavailable', 'Unavailable'),
            ('off_duty', 'Off-duty'),
        ]
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'doctor_blocked_slots'
        ordering = ['blocked_date', 'start_time']
        constraints = [
            models.CheckConstraint(
                check=Q(start_time__lt=F('end_time')),
                name='start_time_before_end_time'
            )
        ]

    def __str__(self):
        return f"{self.doctor} blocked on {self.blocked_date}"
