from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from cloudinary.models import CloudinaryField


ROLE_CHOICES = [
    ('ADMIN', 'Admin'),
    ('CUSTOMER', 'Customer'),
    ('RESTAURANT_USER', 'Restaurant User'),
]

FOLLOW_STATUS_CHOICES = [
    ('FOLLOW', 'Follow'),
    ('CANCEL', 'Cancel'),
]


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    fullname = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    username = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    created_date = models.DateField(auto_now_add=True)
    avatar = CloudinaryField(null=True)
    is_restaurant_user = models.BooleanField(default=False)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    addresses = models.ManyToManyField('Address', related_name='users', blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['fullname', 'username']

    def __str__(self):
        return self.email


class Address(models.Model):
    name = models.CharField(max_length=255, blank=True)
    latitude = models.FloatField()
    longitude = models.FloatField()

    def __str__(self):
        return f"{self.name} ({self.latitude}, {self.longitude})"


class Restaurant(models.Model):
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='restaurants')
    avatar = CloudinaryField(null=True)
    star_rating = models.FloatField(default=0.0)
    address = models.ForeignKey('Address', on_delete=models.SET_NULL, null=True, blank=True, related_name='restaurants')

    def __str__(self):
        return self.name


class Follow(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='follows_as_user')
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='follows_as_restaurant')
    status = models.CharField(max_length=20, choices=FOLLOW_STATUS_CHOICES, default='FOLLOW')

    class Meta:
        unique_together = ('user', 'restaurant')

    def __str__(self):
        return f"{self.user.email} follows {self.restaurant.name} ({self.status})"

    def save(self, *args, **kwargs):
        if self.user.role != 'CUSTOMER':
            raise ValueError("Only users with role CUSTOMER can follow a restaurant.")
        super().save(*args, **kwargs)