from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from cloudinary.models import CloudinaryField
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator

ROLE_CHOICES = [
    ('ADMIN', 'Admin'),
    ('CUSTOMER', 'Customer'),
    ('RESTAURANT_USER', 'Restaurant User'),
]

FOLLOW_STATUS_CHOICES = [
    ('FOLLOW', 'Follow'),
    ('CANCEL', 'Cancel'),
]

FAV_STATUS_CHOICES = [
    ('FAVORITE', 'Favorite'),
    ('CANCEL', 'Cancel'),
]

ORDER_STATUS_CHOICES = [
    ('PENDING', 'Pending'),
    ('ACCEPTED', 'Accepted'),
    ('DELIVERED', 'Delivered'),
    ('CANCEL', 'Cancel'),
    ('FAIL', 'Fail'),
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
        # Đặt giá trị mặc định cho is_approved dựa trên role
        role = extra_fields.get('role', 'CUSTOMER')
        extra_fields.setdefault('is_approved', role != 'RESTAURANT_USER')  # Chỉ RESTAURANT_USER cần phê duyệt

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_approved', True)
        # Không gán role='ADMIN' cho superuser, để role rỗng hoặc một giá trị đặc biệt
        extra_fields.setdefault('role', '')  # Superuser không thuộc ROLE_CHOICES

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    # Các trường mặc định từ AbstractUser: username, first_name, last_name, email, password, is_staff, is_active, date_joined, is_superuser
    email = models.EmailField(unique=True)  # Ghi đè để đảm bảo email là duy nhất
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    avatar = CloudinaryField(null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, blank=True, default='')  # Cho phép role rỗng
    addresses = models.ManyToManyField('Address', related_name='users', blank=True)
    is_approved = models.BooleanField(default=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'  # Sử dụng email thay vì username để đăng nhập
    REQUIRED_FIELDS = ['first_name', 'last_name']  # Các trường bắt buộc khi tạo superuser

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
    owner = models.OneToOneField(User, on_delete=models.CASCADE, related_name='restaurants')
    avatar = CloudinaryField(null=True)
    star_rating = models.FloatField(default=0.0)
    address = models.ForeignKey('Address', on_delete=models.SET_NULL, null=True, blank=True, related_name='restaurants')
    tags = models.ManyToManyField('Tag', related_name='restaurants', blank=True)
    shipping_fee_per_km = models.IntegerField(default=2000)

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

class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fav_as_user')
    food = models.ForeignKey('Food', on_delete=models.CASCADE, related_name='fav_as_food')
    status = models.CharField(max_length=20, choices=FAV_STATUS_CHOICES, default='FAVORITE')

    class Meta:
        unique_together = ('user', 'food')

    def __str__(self):
        return f"{self.user.email} favorite {self.food.name} ({self.status})"

    def save(self, *args, **kwargs):
        if self.user.role != 'CUSTOMER':
            raise ValueError("Only users with role CUSTOMER can add favorite a food.")
        super().save(*args, **kwargs)


class Order(models.Model):
    total = models.FloatField(default=0.0)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='orders')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    address = models.ForeignKey(Address, on_delete=models.CASCADE, related_name='orders')
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='PENDING')
    ordered_date = models.DateField(auto_now_add=True, null=True)
    shipping_fee = models.FloatField(default=0)

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
    sub_total = models.FloatField()  # Giá thực tế tại thời điểm đặt hàng
    time_serve = models.CharField(max_length=20, choices=TIME_SERVE_CHOICES)  # Thêm trường này

    def save(self, *args, **kwargs):
        food_price = FoodPrice.objects.get(food=self.food, time_serve=self.time_serve).price
        self.sub_total = food_price * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f"OrderDetail {self.id} for Order {self.order.id}"


class Payment(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payments')
    payment_method = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='FAIL')
    total_payment = models.FloatField()
    created_date = models.DateField(auto_now_add=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.status == 'FAIL':
            self.order.status = 'FAIL'
            self.order.save()

    def __str__(self):
        return f"Payment {self.id} for Order {self.order.id}"


class FoodCategory(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class Food(models.Model):
    name = models.CharField(max_length=255)
    image = CloudinaryField(null=True)
    description = models.TextField(blank=True, null=True)
    is_available = models.BooleanField(default=True)
    star_rating = models.FloatField(default=0.0)
    food_category = models.ForeignKey(FoodCategory, on_delete=models.CASCADE, related_name='foods')
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='foods')

    def update_star_rating(self):
        order_details = self.order_details.all()
        reviews = FoodReview.objects.filter(order_detail__in=order_details, parent=None)
        if reviews.exists():
            self.star_rating = sum(review.star for review in reviews) / reviews.count()
        else:
            self.star_rating = 0.0
        self.save()

    def __str__(self):
        return self.name


class FoodPrice(models.Model):
    food = models.ForeignKey(Food, on_delete=models.CASCADE, related_name='prices')
    time_serve = models.CharField(max_length=20, choices=TIME_SERVE_CHOICES)
    price = models.FloatField()

    class Meta:
        unique_together = ('food', 'time_serve')

    def __str__(self):
        return f"{self.food.name} - {self.time_serve}: {self.price}"


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

    def clean(self):
        if not Order.objects.filter(user=self.user, restaurant=self.restaurant).exists():
            raise ValidationError("Only users who have placed at least one order at this restaurant can review it.")
        if not (0.0 <= float(self.star) <= 5.0):
            raise ValidationError("Star rating must be between 0.0 and 5.0.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
        # Update restaurant star rating
        reviews = RestaurantReview.objects.filter(restaurant=self.restaurant)
        avg_rating = reviews.aggregate(models.Avg('star'))['star__avg'] or 0.0
        self.restaurant.star_rating = round(avg_rating, 1)
        self.restaurant.save()


class FoodReview(models.Model):
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='food_reviews')
    order_detail = models.ForeignKey('OrderDetail', on_delete=models.CASCADE, related_name='food_reviews')
    comment = models.TextField()
    created_date = models.DateTimeField(auto_now_add=True)
    star = models.DecimalField(max_digits=2, decimal_places=1)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')

    class Meta:
        unique_together = ('user', 'order_detail')

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.parent:  # Logic cho reply
            if self.user.role != 'RESTAURANT_USER':
                raise ValidationError("Only restaurant users can reply to food reviews.")
            if self.order_detail and self.parent.order_detail != self.order_detail:
                raise ValidationError("Replies must belong to the same order detail as the parent review.")
            if self.star != 0:
                raise ValidationError("Replies should not have a star rating.")
        else:  # Logic cho đánh giá gốc
            if not self.order_detail:
                raise ValidationError("Order detail is required for a food review.")
            if self.user != self.order_detail.order.user:
                raise ValidationError("Only the user who placed the order can review the food.")
            if not Order.objects.filter(user=self.user, restaurant=self.order_detail.order.restaurant).exists():
                raise ValidationError("Only users who have placed at least one order at this restaurant can review its food.")
            if not (0.0 <= float(self.star) <= 5.0):
                raise ValidationError("Star rating must be between 0.0 and 5.0.")

    def save(self, *args, **kwargs):
        self.clean()  # Gọi clean để kiểm tra
        super().save(*args, **kwargs)

        if not self.parent:
            food = self.order_detail.food
            food.update_star_rating()

    def __str__(self):
        return f"Food Review by {self.user.email} for {self.order_detail.food.name if self.order_detail else 'Reply'}"


class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='carts')
    item_number = models.IntegerField(default=0)
    total_price = models.FloatField(default=0.0)

    def __str__(self):
        return f"Cart of {self.user.email}"


class SubCart(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='sub_carts')
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='sub_carts')
    total_price = models.FloatField(default=0.0)
    total_quantity = models.IntegerField(default=0)

    def __str__(self):
        return f"SubCart for {self.restaurant.name} in Cart {self.cart.id}"


class SubCartItem(models.Model):
    food = models.ForeignKey(Food, on_delete=models.CASCADE, related_name='sub_cart_items')
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='sub_cart_items')
    sub_cart = models.ForeignKey(SubCart, on_delete=models.CASCADE, related_name='sub_cart_items')
    quantity = models.IntegerField()
    price = models.FloatField()
    time_serve = models.CharField(max_length=20, choices=TIME_SERVE_CHOICES)

    def save(self, *args, **kwargs):
        food_price = FoodPrice.objects.get(food=self.food, time_serve=self.time_serve).price
        self.price = food_price * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f"SubCartItem {self.food.name} in SubCart {self.sub_cart.id}"


# class ChatRoom(models.Model):
#     user1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_rooms_as_user1')
#     user2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_rooms_as_user2')
#     last_message = models.TextField(null=True, blank=True)
#     last_message_time = models.DateTimeField(null=True, blank=True)
#     is_active = models.BooleanField(default=True)
#
#     def __str__(self):
#         return f'Chat between {self.user1.username} and {self.user2.username}'
#
#
# class Message(models.Model):
#     chat_room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
#     sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
#     content = models.TextField()
#     created_date = models.DateTimeField(auto_now_add=True)
#     is_read = models.BooleanField(default=False)
#
#     def __str__(self):
#         return f'Message from {self.sender.username} in {self.chat_room}'

class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('new_menu', 'New Menu'),
        ('new_food', 'New Food Item'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    related_object_id = models.PositiveIntegerField(null=True, blank=True)  # ID của menu hoặc food item
    related_object_type = models.CharField(max_length=50, null=True, blank=True)  # Loại object liên quan

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.notification_type} - {self.user.username} - {self.created_at}"