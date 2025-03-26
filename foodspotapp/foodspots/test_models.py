# File: test_models.py
# Lưu file này trong thư mục E:\BTLON\FoodSpot-Server\foodspotapp\foodspots\test_models.py
# Hướng dẫn chạy:
# 1. Mở terminal, di chuyển đến thư mục chứa manage.py: E:\BTLON\FoodSpot-Server\foodspotapp
# 2. Chạy lệnh: python manage.py shell
# 3. Trong shell, nhập: exec(open('foodspots/test_models.py', encoding='utf-8').read())

# Nhập các model cần thiết
from foodspots.models import (
    User, Address, Restaurant, Follow, Tag, Order, OrderDetail, Payment,
    FoodCategory, Food, Menu, Review, Cart, SubCart, SubCartItem
)

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

# Tạo địa chỉ không thuộc về người dùng (để kiểm tra lỗi)
invalid_address = Address.objects.create(
    name='Invalid Address',
    latitude=10.8000,
    longitude=106.7300
)
print("Đã tạo địa chỉ không thuộc về người dùng:", invalid_address)

# Tạo các thẻ cho nhà hàng
tag1 = Tag.objects.create(name='Fast Food')
tag2 = Tag.objects.create(name='Italian')
print("Đã tạo 2 thẻ:", tag1, tag2)

# Tạo người dùng CUSTOMER và liên kết với địa chỉ
customer = User.objects.create_user(
    email='customer@example.com',
    password='password123',
    fullname='Customer Name',
    username='customer1',
    role='CUSTOMER'
)
customer.addresses.add(address1, address2)
print("Đã tạo CUSTOMER:", customer.email)

# Tạo người dùng CUSTOMER thứ hai và liên kết với địa chỉ
customer2 = User.objects.create_user(
    email='customer2@example.com',
    password='password123',
    fullname='Customer Two',
    username='customer2',
    role='CUSTOMER'
)
customer2.addresses.add(address1)
print("Đã tạo CUSTOMER thứ hai:", customer2.email)

# Tạo người dùng RESTAURANT_USER
restaurant_user = User.objects.create_user(
    email='restaurant@example.com',
    password='password123',
    fullname='Restaurant Owner',
    username='restaurant1',
    role='RESTAURANT_USER',
    is_restaurant_user=True
)
print("Đã tạo RESTAURANT_USER:", restaurant_user.email)

# Tạo một nhà hàng với địa chỉ và thẻ
restaurant = Restaurant.objects.create(
    name='Restaurant A',
    phone_number='1234567890',
    owner=restaurant_user,
    star_rating=4.5,
    address=restaurant_address
)
restaurant.tags.add(tag1, tag2)
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
print("Đã tạo danh mục món ăn:", food_category)

# Tạo món ăn
food1 = Food.objects.create(
    name='Pizza',
    price=10.0,
    description='Delicious pizza with cheese',
    is_available=True,
    time_serve='NOON',
    star_rating=4.0,
    food_category=food_category
)
food2 = Food.objects.create(
    name='Pasta',
    price=8.0,
    description='Creamy pasta with sauce',
    is_available=True,
    time_serve='EVENING',
    star_rating=4.2,
    food_category=food_category
)
print("Đã tạo 2 món ăn:", food1, food2)

# Tạo menu cho nhà hàng
menu = Menu.objects.create(
    restaurant=restaurant,
    name='Lunch Menu',
    description='Menu for lunch time',
    time_serve='NOON'
)
menu.foods.add(food1, food2)
print("Đã tạo menu:", menu)

# Tạo giỏ hàng cho người dùng
cart = Cart.objects.create(user=customer, item_number=0)
print("Đã tạo giỏ hàng:", cart)

# Tạo sub-cart cho nhà hàng
sub_cart = SubCart.objects.create(cart=cart, restaurant=restaurant, total_price=0.0)
print("Đã tạo sub-cart:", sub_cart)

# Tạo sub-cart item
sub_cart_item1 = SubCartItem.objects.create(
    food=food1,
    restaurant=restaurant,
    sub_cart=sub_cart,
    quantity=2,
    price=food1.price * 2
)
sub_cart_item2 = SubCartItem.objects.create(
    food=food2,
    restaurant=restaurant,
    sub_cart=sub_cart,
    quantity=1,
    price=food2.price
)
sub_cart.total_price = sub_cart_item1.price + sub_cart_item2.price
sub_cart.save()
cart.item_number = 3  # 2 Pizza + 1 Pasta
cart.save()
print("Đã tạo sub-cart items:", sub_cart_item1, sub_cart_item2)

# Tạo đơn hàng đầu tiên với địa chỉ hợp lệ
order1 = Order.objects.create(
    delivery_status=1,
    total=0.0,
    restaurant=restaurant,
    user=customer,
    address=address1,
    status='PENDING'
)
order_detail1 = OrderDetail.objects.create(
    order=order1,
    food=food1,
    quantity=2,
    sub_total=food1.price * 2
)
order_detail2 = OrderDetail.objects.create(
    order=order1,
    food=food2,
    quantity=1,
    sub_total=food2.price
)
order1.total = order_detail1.sub_total + order_detail2.sub_total
order1.save()
print("Đã tạo đơn hàng đầu tiên:", order1)

# Tạo đơn hàng thứ hai với cùng món ăn Pizza
order2 = Order.objects.create(
    delivery_status=1,
    total=0.0,
    restaurant=restaurant,
    user=customer,
    address=address2,
    status='PENDING'
)
order_detail3 = OrderDetail.objects.create(
    order=order2,
    food=food1,  # Cùng món Pizza
    quantity=1,
    sub_total=food1.price
)
order2.total = order_detail3.sub_total
order2.save()
print("Đã tạo đơn hàng thứ hai:", order2)

# Thử tạo đơn hàng với địa chỉ không hợp lệ
try:
    invalid_order = Order.objects.create(
        delivery_status=1,
        total=0.0,
        restaurant=restaurant,
        user=customer,
        address=invalid_address,
        status='PENDING'
    )
except ValueError as e:
    print("Lỗi khi tạo đơn hàng với địa chỉ không hợp lệ:", e)

# Tạo thanh toán cho đơn hàng đầu tiên
payment1 = Payment.objects.create(
    order=order1,
    payment_method='Credit Card',
    status='SUCCESS',
    amount=order1.total,
    total_payment=order1.total
)
print("Đã tạo thanh toán cho đơn hàng đầu tiên:", payment1)

# Tạo thanh toán cho đơn hàng thứ hai
payment2 = Payment.objects.create(
    order=order2,
    payment_method='Credit Card',
    status='SUCCESS',
    amount=order2.total,
    total_payment=order2.total
)
print("Đã tạo thanh toán cho đơn hàng thứ hai:", payment2)

# Tạo đánh giá cho Pizza trong đơn hàng đầu tiên
review1 = Review.objects.create(
    user=customer,
    order_detail=order_detail1,
    comment='Great pizza!',
    star=4.5
)
print("Đã tạo đánh giá cho Pizza trong đơn hàng đầu tiên:", review1)

# Tạo đánh giá cho Pizza trong đơn hàng thứ hai
review2 = Review.objects.create(
    user=customer,
    order_detail=order_detail3,
    comment='Not as good this time.',
    star=3.0
)
print("Đã tạo đánh giá cho Pizza trong đơn hàng thứ hai:", review2)

# Thử tạo đánh giá thứ hai cho cùng một OrderDetail (nên thất bại)
try:
    invalid_review = Review.objects.create(
        user=customer,
        order_detail=order_detail1,
        comment='Trying to review again.',
        star=2.0
    )
except Exception as e:
    print("Lỗi khi tạo đánh giá thứ hai cho cùng một OrderDetail:", e)

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

# Kiểm tra địa chỉ của nhà hàng
print("\nĐịa chỉ của", restaurant.name, ":")
if restaurant.address:
    print(restaurant.address.name, restaurant.address.latitude, restaurant.address.longitude)
else:
    print("Nhà hàng không có địa chỉ")

# Kiểm tra danh sách thẻ của nhà hàng
print("\nDanh sách thẻ của", restaurant.name, ":")
tags = restaurant.tags.all()
for tag in tags:
    print(tag.name)

# Kiểm tra danh sách nhà hàng có thẻ tag1
print("\nDanh sách nhà hàng có thẻ", tag1.name, ":")
restaurants_with_tag = tag1.restaurants.all()
for restaurant in restaurants_with_tag:
    print(restaurant.name)

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

# Kiểm tra danh sách món ăn trong danh mục
print("\nDanh sách món ăn trong danh mục", food_category.name, ":")
foods = food_category.foods.all()
for food in foods:
    print(food.name, food.price)

# Kiểm tra danh sách món ăn trong menu
print("\nDanh sách món ăn trong menu", menu.name, ":")
foods = menu.foods.all()
for food in foods:
    print(food.name)

# Kiểm tra giỏ hàng
print("\nGiỏ hàng của", customer.email, ":")
print(f"Số lượng món: {cart.item_number}")
sub_carts = cart.sub_carts.all()
for sub_cart in sub_carts:
    print(f"SubCart cho nhà hàng {sub_cart.restaurant.name}: Tổng giá {sub_cart.total_price}")
    for item in sub_cart.sub_cart_items.all():
        print(f"  - {item.food.name}: Số lượng {item.quantity}, Giá {item.price}")

# Kiểm tra đơn hàng
print("\nĐơn hàng của", customer.email, ":")
orders = customer.orders.all()
for order in orders:
    print(f"Đơn hàng {order.id} tại {order.restaurant.name}: Tổng {order.total}, Trạng thái {order.status}")
    print(f"Địa chỉ giao hàng: {order.address.name} ({order.address.latitude}, {order.address.longitude})")
    for detail in order.order_details.all():
        print(f"  - {detail.food.name}: Số lượng {detail.quantity}, Tạm tính {detail.sub_total}")
        if hasattr(detail, 'review'):
            print(f"    Đánh giá: {detail.review.comment}, {detail.review.star} sao")
    for payment in order.payments.all():
        print(f"Thanh toán: Phương thức {payment.payment_method}, Trạng thái {payment.status}, Số tiền {payment.total_payment}")

# Kiểm tra đánh giá
print("\nĐánh giá của", customer.email, ":")
reviews = customer.reviews.all()
for review in reviews:
    print(f"Đánh giá cho {review.order_detail.food.name} trong đơn hàng {review.order_detail.order.id}: {review.comment}, {review.star} sao")

# Kiểm tra danh sách nhà hàng của restaurant_user
print("\nDanh sách nhà hàng của", restaurant_user.email, ":")
restaurants = restaurant_user.restaurants.all()
for restaurant in restaurants:
    print(restaurant.name, restaurant.star_rating)
    if restaurant.address:
        print("Địa chỉ:", restaurant.address.name, restaurant.address.latitude, restaurant.address.longitude)

print("\n=== Kết thúc test ===")