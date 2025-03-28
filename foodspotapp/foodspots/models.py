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

ORDER_STATUS_CHOICES = [
    ('PENDING', 'Pending'),
    ('ACCEPTED', 'Accepted'),
    ('DELIVERED', 'Delivered'),
    ('CANCEL', 'Cancel'),
]

PAYMENT_STATUS_CHOICES = [
    ('SUCCESS', 'Success'),
    ('FAIL', 'Fail'),
]

TIME_SERVE_CHOICES = [
    ('MORNING', 'Morning'),
    ('NOON', 'Noon'),
    ('EVENING', 'Evening'),
    ('NIGHT', 'Night'),
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


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class Restaurant(models.Model):
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='restaurants')
    avatar = CloudinaryField(null=True)
    star_rating = models.FloatField(default=0.0)
    address = models.ForeignKey('Address', on_delete=models.SET_NULL, null=True, blank=True, related_name='restaurants')
    tags = models.ManyToManyField('Tag', related_name='restaurants', blank=True)

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


class Order(models.Model):
    delivery_status = models.IntegerField(default=0)
    total = models.FloatField(default=0.0)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='orders')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    address = models.ForeignKey(Address, on_delete=models.CASCADE, related_name='orders')
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='PENDING')

    def __str__(self):
        return f"Order {self.id} by {self.user.email} at {self.restaurant.name}"

    def save(self, *args, **kwargs):
        if self.address not in self.user.addresses.all():
            raise ValueError("The selected address must be one of the user's addresses.")
        super().save(*args, **kwargs)


class OrderDetail(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='order_details')
    food = models.ForeignKey('Food', on_delete=models.CASCADE, related_name='order_details')
    quantity = models.IntegerField()
    sub_total = models.FloatField()

    def __str__(self):
        return f"OrderDetail {self.id} for Order {self.order.id}"


class Payment(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payments')
    payment_method = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='FAIL')
    amount = models.FloatField()
    total_payment = models.FloatField()
    created_date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"Payment {self.id} for Order {self.order.id}"


class FoodCategory(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class Food(models.Model):
    name = models.CharField(max_length=255)
    price = models.FloatField()
    image = CloudinaryField(null=True)
    description = models.TextField(blank=True, null=True)
    is_available = models.BooleanField(default=True)
    time_serve = models.CharField(max_length=20, choices=TIME_SERVE_CHOICES)
    star_rating = models.FloatField(default=0.0)
    food_category = models.ForeignKey(FoodCategory, on_delete=models.CASCADE, related_name='foods')

    def update_star_rating(self):
        # Chỉ lấy các đánh giá gốc (parent=None)
        reviews = FoodReview.objects.filter(order_detail__food=self, parent=None)
        if reviews.exists():
            # Tính trung bình star của các đánh giá gốc
            avg_rating = reviews.aggregate(models.Avg('star'))['star__avg']
            self.star_rating = round(avg_rating, 1)
        else:
            self.star_rating = 0.0
        self.save()

    def __str__(self):
        return self.name


class Menu(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='menus')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    time_serve = models.CharField(max_length=20, choices=TIME_SERVE_CHOICES)
    foods = models.ManyToManyField(Food, related_name='menus')

    def __str__(self):
        return f"{self.name} at {self.restaurant.name}"


class RestaurantReview(models.Model):
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='restaurant_reviews')
    restaurant = models.ForeignKey('Restaurant', on_delete=models.CASCADE, related_name='restaurant_reviews')
    comment = models.TextField()
    created_date = models.DateTimeField(auto_now_add=True)
    star = models.DecimalField(max_digits=2, decimal_places=1)

    class Meta:
        unique_together = ('user', 'restaurant')

    def __str__(self):
        return f"Restaurant Review by {self.user.email} for {self.restaurant.name} (Star: {self.star})"

    def save(self, *args, **kwargs):
        if not Order.objects.filter(user=self.user, restaurant=self.restaurant).exists():
            raise ValueError("Only users who have placed at least one order at this restaurant can review it.")
        if not (0.0 <= float(self.star) <= 5.0):
            raise ValueError("Star rating must be between 0.0 and 5.0.")
        super().save(*args, **kwargs)


class FoodReview(models.Model):
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='food_reviews')
    order_detail = models.ForeignKey('OrderDetail', on_delete=models.CASCADE, related_name='food_reviews')
    comment = models.TextField()
    created_date = models.DateTimeField(auto_now_add=True)
    star = models.DecimalField(max_digits=2, decimal_places=1)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')

    class Meta:
        unique_together = ('user', 'order_detail')

    def save(self, *args, **kwargs):
        if self.parent:
            if self.user.role != 'RESTAURANT_USER':
                raise ValueError("Only restaurant users can reply to food reviews.")
            if self.parent.order_detail != self.order_detail:
                raise ValueError("Replies must belong to the same order detail as the parent review.")
            if self.star != 0:
                raise ValueError("Replies should not have a star rating.")
        else:
            if self.user != self.order_detail.order.user:
                raise ValueError("Only the user who placed the order can review the food.")
            if not Order.objects.filter(user=self.user, restaurant=self.order_detail.order.restaurant).exists():
                raise ValueError("Only users who have placed at least one order at this restaurant can review its food.")
            if not (0.0 <= float(self.star) <= 5.0):
                raise ValueError("Star rating must be between 0.0 and 5.0.")
        super().save(*args, **kwargs)


class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='carts')
    item_number = models.IntegerField(default=0)

    def __str__(self):
        return f"Cart of {self.user.email}"


class SubCart(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='sub_carts')
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='sub_carts')
    total_price = models.FloatField(default=0.0)

    def __str__(self):
        return f"SubCart for {self.restaurant.name} in Cart {self.cart.id}"


class SubCartItem(models.Model):
    food = models.ForeignKey(Food, on_delete=models.CASCADE, related_name='sub_cart_items')
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='sub_cart_items')
    sub_cart = models.ForeignKey(SubCart, on_delete=models.CASCADE, related_name='sub_cart_items')
    quantity = models.IntegerField()
    price = models.FloatField()

    def __str__(self):
        return f"SubCartItem {self.food.name} in SubCart {self.sub_cart.id}"