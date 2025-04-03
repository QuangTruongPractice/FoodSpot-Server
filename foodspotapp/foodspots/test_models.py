# File: foodspots/test_models.py
# Hướng dẫn chạy:
# 1. Mở terminal, di chuyển đến thư mục chứa manage.py: E:\BTLON\FoodSpot-Server\foodspotapp
# 2. Chạy lệnh: python manage.py shell
# 3. Trong shell, nhập: exec(open('foodspots/test_models.py', encoding='utf-8').read())

# Nhập các model cần thiết
from foodspots.models import User, Address, Tag, Restaurant, Follow, Order, OrderDetail, Payment, FoodCategory, Food, Menu, RestaurantReview, FoodReview, Cart, SubCart, SubCartItem
from decimal import Decimal
from django.db import models

# Bước 1: Tạo dữ liệu test
print("=== Bắt đầu tạo dữ liệu test ===")

# Tạo các địa chỉ cho người dùng
address1 = Address.objects.create(
    name='Home Address',
    latitude=10.7769,
    longitude=106.7009
)
address2 = Address.objects.create(
    name='Work Address',
    latitude=10.7800,
    longitude=106.7100
)
print("Đã tạo 2 địa chỉ cho người dùng:", address1, address2)

# Tạo địa chỉ cho nhà hàng
restaurant_address = Address.objects.create(
    name='Restaurant A Address',
    latitude=10.7900,
    longitude=106.7200
)
print("Đã tạo địa chỉ cho nhà hàng:", restaurant_address)

# Tạo người dùng CUSTOMER và liên kết với địa chỉ
customer = User.objects.create_user(
    email='customer@example.com',
    password='password123',
    first_name='Customer',
    last_name='Name',
    username='customer1',  # Thêm username duy nhất
    role='CUSTOMER'
)
admin = User.objects.create_user(
    email='customer@example.com',
    password='password123',
    first_name='Customer',
    last_name='Name',
    username='customer1',  # Thêm username duy nhất
    role='CUSTOMER'
)
customer.addresses.add(address1, address2)
print("Đã tạo CUSTOMER:", customer.email)

# Tạo người dùng CUSTOMER thứ hai và liên kết với địa chỉ
customer2 = User.objects.create_user(
    email='customer2@example.com',
    password='password123',
    first_name='Customer',
    last_name='Two',
    username='customer2',  # Thêm username duy nhất
    role='CUSTOMER'
)
customer2.addresses.add(address1)
print("Đã tạo CUSTOMER thứ hai:", customer2.email)

# Tạo người dùng RESTAURANT_USER
restaurant_user = User.objects.create_user(
    email='restaurant@example.com',
    password='password123',
    first_name='Restaurant',
    last_name='Owner',
    username='restaurant1',  # Thêm username duy nhất
    role='RESTAURANT_USER',
)
print("Đã tạo RESTAURANT_USER:", restaurant_user.email)

# Tạo tag
tag = Tag.objects.create(name='Fast Food')
print("Đã tạo Tag:", tag)

# Tạo nhà hàng
restaurant = Restaurant.objects.create(
    name='Restaurant A',
    phone_number='1234567890',
    owner=restaurant_user,
    star_rating=4.5,
    address=restaurant_address
)
restaurant.tags.add(tag)
print("Đã tạo nhà hàng:", restaurant.name)

# Tạo mối quan hệ Follow
follow = Follow.objects.create(
    user=customer,
    restaurant=restaurant,
    status='FOLLOW'
)
print("Đã tạo mối quan hệ Follow:", follow)

# Tạo danh mục món ăn
food_category = FoodCategory.objects.create(name='Main Course')
print("Đã tạo FoodCategory:", food_category)

# Tạo món ăn
food = Food.objects.create(
    name='Pizza',
    price=15.00,
    description='Delicious pizza with cheese',
    time_serve='EVENING',
    star_rating=0.0,  # Ban đầu là 0, sẽ được cập nhật sau khi có đánh giá
    food_category=food_category
)
print("Đã tạo Food:", food)

# Tạo menu
menu = Menu.objects.create(
    restaurant=restaurant,
    name='Dinner Menu',
    description='Menu for dinner',
    time_serve='EVENING'
)
menu.foods.add(food)
print("Đã tạo Menu:", menu)

# Tạo giỏ hàng
cart = Cart.objects.create(
    user=customer,
    item_number=1
)
print("Đã tạo Cart:", cart)

# Tạo SubCart
sub_cart = SubCart.objects.create(
    cart=cart,
    restaurant=restaurant,
    total_price=30.00
)
print("Đã tạo SubCart:", sub_cart)

# Tạo SubCartItem
sub_cart_item = SubCartItem.objects.create(
    food=food,
    restaurant=restaurant,
    sub_cart=sub_cart,
    quantity=2,
    price=30.00
)
print("Đã tạo SubCartItem:", sub_cart_item)

# Tạo đơn hàng cho customer
order = Order.objects.create(
    user=customer,
    restaurant=restaurant,
    address=address1,
    total=20.00,
    status='DELIVERED'
)
print("Đã tạo Order:", order)

# Tạo chi tiết đơn hàng
order_detail = OrderDetail.objects.create(
    order=order,
    food=food,
    quantity=2,
    sub_total=30.00
)
print("Đã tạo OrderDetail:", order_detail)

# Tạo thanh toán
payment = Payment.objects.create(
    order=order,
    payment_method='Credit Card',
    status='SUCCESS',
    amount=30.00,
    total_payment=30.00
)
print("Đã tạo Payment:", payment)

# Tạo đánh giá nhà hàng từ customer (có đơn hàng)
restaurant_review = RestaurantReview.objects.create(
    user=customer,
    restaurant=restaurant,
    star=Decimal('4.8'),
    comment="Great food and service!"
)
print("Đã tạo Restaurant Review:", restaurant_review)

# Tạo đánh giá món ăn từ customer (có đơn hàng)
food_review1 = FoodReview.objects.create(
    user=customer,
    order_detail=order_detail,
    star=Decimal('4.5'),
    comment="The pizza was delicious!"
)
print("Đã tạo Food Review 1:", food_review1)

# Cập nhật star_rating của món ăn sau khi có đánh giá
food.update_star_rating()
print(f"Star rating của {food.name} sau 1 đánh giá: {food.star_rating} (Dự kiến: 4.5)")

# Tạo một đánh giá món ăn khác từ customer (giả sử customer đặt thêm đơn hàng)
order2 = Order.objects.create(
    user=customer,
    restaurant=restaurant,
    address=address1,
    total=15.00,
    status='DELIVERED'
)
order_detail2 = OrderDetail.objects.create(
    order=order2,
    food=food,
    quantity=1,
    sub_total=15.00
)
food_review2 = FoodReview.objects.create(
    user=customer,
    order_detail=order_detail2,
    star=Decimal('5.0'),
    comment="Amazing pizza!"
)
print("Đã tạo Food Review 2:", food_review2)

# Cập nhật star_rating của món ăn sau khi có thêm đánh giá
food.update_star_rating()
print(f"Star rating của {food.name} sau 2 đánh giá: {food.star_rating} (Dự kiến: (4.5 + 5.0) / 2 = 4.8)")

# Tạo reply từ restaurant_user cho food_review1
food_review_reply = FoodReview.objects.create(
    user=restaurant_user,
    order_detail=order_detail,
    comment="Thank you for your review! We're glad you enjoyed the pizza.",
    star=Decimal('0.0'),  # Reply không có star
    parent=food_review1
)
print("Đã tạo Food Review Reply:", food_review_reply)

# Cập nhật star_rating của món ăn sau khi có reply
food.update_star_rating()
print(f"Star rating của {food.name} sau khi có reply: {food.star_rating} (Dự kiến: vẫn là 4.8, vì reply không ảnh hưởng)")

# Thử tạo reply từ customer (không được phép)
try:
    invalid_food_review_reply = FoodReview.objects.create(
        user=customer2,
        order_detail=order_detail,
        comment="I also liked the pizza!",
        star=Decimal('0.0'),
        parent=food_review1
    )
except ValueError as e:
    print("Lỗi khi tạo Food Review Reply từ customer:", e)

# Thử tạo reply với star (không được phép)
try:
    invalid_food_review_reply_star = FoodReview.objects.create(
        user=restaurant_user,
        order_detail=order_detail,
        comment="Thank you!",
        star=Decimal('3.0'),  # Reply không được có star
        parent=food_review1
    )
except ValueError as e:
    print("Lỗi khi tạo Food Review Reply với star:", e)

# Thử tạo reply cho order_detail khác (không được phép)
try:
    invalid_food_review_reply_order = FoodReview.objects.create(
        user=restaurant_user,
        order_detail=order_detail2,
        comment="Thank you!",
        star=Decimal('0.0'),
        parent=food_review1
    )
except ValueError as e:
    print("Lỗi khi tạo Food Review Reply cho order_detail khác:", e)

# Thử tạo đánh giá nhà hàng từ customer2 (không có đơn hàng)
try:
    invalid_restaurant_review = RestaurantReview.objects.create(
        user=customer2,
        restaurant=restaurant,
        star=Decimal('3.5'),
        comment="Not bad"
    )
except ValueError as e:
    print("Lỗi khi tạo Restaurant Review từ", customer2.email, ":", e)

# Thử tạo đánh giá món ăn từ customer2 (không phải người đặt đơn hàng)
try:
    invalid_food_review = FoodReview.objects.create(
        user=customer2,
        order_detail=order_detail,
        star=Decimal('3.0'),
        comment="Pizza was okay"
    )
except ValueError as e:
    print("Lỗi khi tạo Food Review từ", customer2.email, ":", e)

# Thử tạo đánh giá nhà hàng với star không hợp lệ (quá lớn)
try:
    invalid_star_restaurant_review = RestaurantReview.objects.create(
        user=customer,
        restaurant=restaurant,
        star=Decimal('6.0'),  # Quá lớn
        comment="Invalid star rating"
    )
except ValueError as e:
    print("Lỗi khi tạo Restaurant Review với star không hợp lệ:", e)

# Thử tạo đánh giá món ăn với star không hợp lệ (quá nhỏ)
try:
    invalid_star_food_review = FoodReview.objects.create(
        user=customer,
        order_detail=order_detail,
        star=Decimal('-1.0'),  # Quá nhỏ
        comment="Invalid star rating"
    )
except ValueError as e:
    print("Lỗi khi tạo Food Review với star không hợp lệ:", e)

# Thử tạo một Follow với người dùng không phải CUSTOMER
try:
    invalid_follow = Follow.objects.create(
        user=restaurant_user,
        restaurant=restaurant,
        status='FOLLOW'
    )
except ValueError as e:
    print("Lỗi khi tạo Follow với RESTAURANT_USER:", e)

# Thử tạo một Order với địa chỉ không thuộc user
try:
    invalid_order = Order.objects.create(
        user=customer2,
        restaurant=restaurant,
        address=address2,  # address2 không thuộc customer2
        total=20.00,
        status='PENDING'
    )
except ValueError as e:
    print("Lỗi khi tạo Order với địa chỉ không hợp lệ:", e)

# Bước 2: Truy vấn và kiểm tra dữ liệu
print("\n=== Kiểm tra dữ liệu ===")

# Kiểm tra danh sách địa chỉ của customer
print("\nDanh sách địa chỉ của", customer.email, ":")
addresses = customer.addresses.all()
for address in addresses:
    print(address.name, address.latitude, address.longitude)

# Kiểm tra danh sách người dùng sử dụng address1
print("\nDanh sách người dùng sử dụng", address1.name, ":")
users = address1.users.all()
for user in users:
    print(user.email)

# Kiểm tra danh sách tag của restaurant
print("\nDanh sách tag của", restaurant.name, ":")
tags = restaurant.tags.all()
for tag in tags:
    print(tag.name)

# Kiểm tra địa chỉ của nhà hàng
print("\nĐịa chỉ của", restaurant.name, ":")
if restaurant.address:
    print(restaurant.address.name, restaurant.address.latitude, restaurant.address.longitude)
else:
    print("Nhà hàng không có địa chỉ")

# Kiểm tra danh sách món ăn trong menu
print("\nDanh sách món ăn trong", menu.name, ":")
foods = menu.foods.all()
for food in foods:
    print(food.name, food.price)

# Kiểm tra danh sách menu của restaurant
print("\nDanh sách menu của", restaurant.name, ":")
menus = restaurant.menus.all()
for menu in menus:
    print(menu.name, menu.time_serve)

# Kiểm tra danh sách món ăn trong food_category
print("\nDanh sách món ăn trong", food_category.name, ":")
foods = food_category.foods.all()
for food in foods:
    print(food.name, food.price)

# Kiểm tra danh sách giỏ hàng của customer
print("\nDanh sách giỏ hàng của", customer.email, ":")
carts = customer.carts.all()
for cart in carts:
    print(cart, cart.item_number)

# Kiểm tra danh sách SubCart của cart
print("\nDanh sách SubCart của", cart, ":")
sub_carts = cart.sub_carts.all()
for sub_cart in sub_carts:
    print(sub_cart, sub_cart.total_price)

# Kiểm tra danh sách SubCartItem của sub_cart
print("\nDanh sách SubCartItem của", sub_cart, ":")
sub_cart_items = sub_cart.sub_cart_items.all()
for item in sub_cart_items:
    print(item, item.quantity, item.price)

# Kiểm tra danh sách đơn hàng của customer
print("\nDanh sách đơn hàng của", customer.email, ":")
orders = customer.orders.all()
for order in orders:
    print(order, order.total, order.status)

# Kiểm tra chi tiết đơn hàng
print("\nDanh sách chi tiết đơn hàng của", order, ":")
order_details = order.order_details.all()
for detail in order_details:
    print(detail, detail.quantity, detail.sub_total)

# Kiểm tra đánh giá món ăn trong order_detail
print("\nDanh sách đánh giá món ăn trong", order_detail, ":")
food_reviews = order_detail.food_reviews.all()
for review in food_reviews:
    print(review, review.comment)
    # Kiểm tra các reply của đánh giá
    replies = review.replies.all()
    for reply in replies:
        print(f"  Reply: {reply}, {reply.comment}")

# Kiểm tra thanh toán của đơn hàng
print("\nDanh sách thanh toán của", order, ":")
payments = order.payments.all()
for payment in payments:
    print(payment, payment.payment_method, payment.status)

# Kiểm tra danh sách đánh giá nhà hàng của restaurant
print("\nDanh sách đánh giá nhà hàng của", restaurant.name, ":")
restaurant_reviews = restaurant.restaurant_reviews.all()
for review in restaurant_reviews:
    print(review, review.comment)

# Kiểm tra danh sách nhà hàng mà customer theo dõi
print("\nDanh sách nhà hàng mà", customer.email, "theo dõi:")
followed_restaurants = customer.follows_as_user.all()
for follow in followed_restaurants:
    print(follow.restaurant.name, follow.status)

# Kiểm tra danh sách người dùng theo dõi restaurant
print("\nDanh sách người dùng theo dõi", restaurant.name, ":")
followers = restaurant.follows_as_restaurant.all()
for follow in followers:
    print(follow.user.email, follow.status)

# Kiểm tra danh sách nhà hàng của restaurant_user
print("\nDanh sách nhà hàng của", restaurant_user.email, ":")
restaurants = restaurant_user.restaurants.all()
for restaurant in restaurants:
    print(restaurant.name, restaurant.star_rating)
    if restaurant.address:
        print("Địa chỉ:", restaurant.address.name, restaurant.address.latitude, restaurant.address.longitude)

print("\n=== Kết thúc test ===")