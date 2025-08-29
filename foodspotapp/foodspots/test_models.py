# File: foodspots/test_models.py
# Hướng dẫn chạy:
# 1. Mở terminal, di chuyển đến thư mục chứa manage.py: E:\new2clienttruong\FoodSpot-Server\foodspotapp
# 2. Chạy lệnh: python manage.py shell
# 3. Trong shell, nhập: exec(open('foodspots/test_models.py', encoding='utf-8').read())

# Nhập các model cần thiết
from foodspots.models import User, Address, Tag, Restaurant, Follow, Order, OrderDetail, Payment, FoodCategory, Food, FoodPrice, Menu, RestaurantReview, FoodReview, Cart, SubCart, SubCartItem
from decimal import Decimal
from django.db import models

# Bước 1: Xóa dữ liệu cũ (tùy chọn, chỉ dùng trong môi trường test)
print("=== Xóa dữ liệu cũ ===")
User.objects.all().delete()
Address.objects.all().delete()
Tag.objects.all().delete()
Restaurant.objects.all().delete()
FoodCategory.objects.all().delete()
Food.objects.all().delete()
FoodPrice.objects.all().delete()
Order.objects.all().delete()
OrderDetail.objects.all().delete()
Payment.objects.all().delete()
Follow.objects.all().delete()
Menu.objects.all().delete()
RestaurantReview.objects.all().delete()
FoodReview.objects.all().delete()
Cart.objects.all().delete()
SubCart.objects.all().delete()
SubCartItem.objects.all().delete()

# Bước 1: Tạo dữ liệu test
print("\n=== Bắt đầu tạo dữ liệu test ===")

# Tạo các địa chỉ cho người dùng
address1 = Address.objects.create(
    name='Nhà riêng',
    latitude=10.7769,
    longitude=106.7009
)
address2 = Address.objects.create(
    name='Cơ quan',
    latitude=10.7800,
    longitude=106.7100
)
print("Đã tạo 2 địa chỉ cho người dùng:", address1, address2)

# Tạo địa chỉ cho nhà hàng
restaurant_address1 = Address.objects.create(
    name='Quán ăn Sài Gòn',
    latitude=10.7900,
    longitude=106.7200
)
restaurant_address2 = Address.objects.create(
    name='Nhà hàng Hà Nội',
    latitude=21.0285,
    longitude=105.8542
)
print("Đã tạo địa chỉ cho nhà hàng:", restaurant_address1, restaurant_address2)

# Tạo người dùng CUSTOMER và liên kết với địa chỉ
customer = User.objects.create_user(
    email='khachhang1@example.com',
    password='matkhau123',
    first_name='Nguyễn',
    last_name='Văn A',
    username='khachhang1',
    role='CUSTOMER'
)
customer.addresses.add(address1, address2)
print("Đã tạo CUSTOMER:", customer.email)

# Tạo người dùng CUSTOMER thứ hai
customer2 = User.objects.create_user(
    email='khachhang2@example.com',
    password='matkhau123',
    first_name='Trần',
    last_name='Thị B',
    username='khachhang2',
    role='CUSTOMER'
)
customer2.addresses.add(address1)
print("Đã tạo CUSTOMER thứ hai:", customer2.email)

# Tạo người dùng RESTAURANT_USER
restaurant_user = User.objects.create_user(
    email='chuquan@example.com',
    password='matkhau123',
    first_name='Lê',
    last_name='Văn C',
    username='chuquan1',
    role='RESTAURANT_USER'
)
print("Đã tạo RESTAURANT_USER:", restaurant_user.email, "Role:", restaurant_user.role)

# Tạo người dùng RESTAURANT_USER thứ hai cho restaurant2
restaurant_user2 = User.objects.create_user(
    email='chuquan2@example.com',
    password='matkhau123',
    first_name='Trần',
    last_name='Văn D',
    username='chuquan2',
    role='RESTAURANT_USER'
)
print("Đã tạo RESTAURANT_USER thứ hai:", restaurant_user2.email)

# Tạo tag
tag1 = Tag.objects.create(name='Ẩm thực Việt')
tag2 = Tag.objects.create(name='Đồ uống')
print("Đã tạo Tag:", tag1, tag2)

# Tạo nhà hàng
restaurant1 = Restaurant.objects.create(
    name='Quán Phở Sài Gòn',
    phone_number='0909123456',
    owner=restaurant_user,
    star_rating=4.7,
    address=restaurant_address1
)
restaurant1.tags.add(tag1)
print("Đã tạo nhà hàng:", restaurant1.name)

restaurant2 = Restaurant.objects.create(
    name='Trà Sữa Nhà Làm',
    phone_number='0918234567',
    owner=restaurant_user2,
    star_rating=4.3,
    address=restaurant_address2
)
restaurant2.tags.add(tag2)
print("Đã tạo nhà hàng:", restaurant2.name)

# Tạo mối quan hệ Follow
follow = Follow.objects.create(
    user=customer,
    restaurant=restaurant1,
    status='FOLLOW'
)
print("Đã tạo mối quan hệ Follow:", follow)

# Tạo danh mục món ăn
food_category1 = FoodCategory.objects.create(name='Món chính')
food_category2 = FoodCategory.objects.create(name='Đồ uống')
print("Đã tạo FoodCategory:", food_category1, food_category2)

# Tạo món ăn
food1 = Food.objects.create(
    name='Phở Bò',
    description='Phở bò truyền thống với nước dùng thơm ngon',
    is_available=True,
    star_rating=0.0,
    food_category=food_category1,
    restaurant=restaurant1
)
FoodPrice.objects.create(food=food1, time_serve='MORNING', price=40000)
FoodPrice.objects.create(food=food1, time_serve='EVENING', price=45000)

food2 = Food.objects.create(
    name='Trà Sữa Trân Châu',
    description='Trà sữa thơm ngon với trân châu dai giòn',
    is_available=True,
    star_rating=0.0,
    food_category=food_category2,
    restaurant=restaurant2
)
FoodPrice.objects.create(food=food2, time_serve='NOON', price=30000)
FoodPrice.objects.create(food=food2, time_serve='NIGHT', price=35000)
print("Đã tạo Food:", food1, food2)

# Tạo menu
menu1 = Menu.objects.create(
    restaurant=restaurant1,
    name='Thực đơn buổi tối',
    description='Các món ăn phục vụ buổi tối',
    time_serve='EVENING'
)
menu1.foods.add(food1)
menu2 = Menu.objects.create(
    restaurant=restaurant2,
    name='Thực đơn đêm',
    description='Đồ uống phục vụ buổi đêm',
    time_serve='NIGHT'
)
menu2.foods.add(food2)
print("Đã tạo Menu:", menu1, menu2)

# Tạo giỏ hàng
cart = Cart.objects.create(
    user=customer,
    item_number=2
)
print("Đã tạo Cart:", cart)

# Tạo SubCart
sub_cart1 = SubCart.objects.create(
    cart=cart,
    restaurant=restaurant1,
    total_price=90000
)
sub_cart2 = SubCart.objects.create(
    cart=cart,
    restaurant=restaurant2,
    total_price=70000
)
print("Đã tạo SubCart:", sub_cart1, sub_cart2)

# Tạo SubCartItem
sub_cart_item1 = SubCartItem.objects.create(
    food=food1,
    restaurant=restaurant1,
    sub_cart=sub_cart1,
    quantity=2,
    price=45000,  # Giá buổi tối
    time_serve='EVENING'
)
sub_cart_item2 = SubCartItem.objects.create(
    food=food2,
    restaurant=restaurant2,
    sub_cart=sub_cart2,
    quantity=2,
    price=35000,  # Giá buổi đêm
    time_serve='NIGHT'
)
print("Đã tạo SubCartItem:", sub_cart_item1, sub_cart_item2)

# Tạo đơn hàng
order = Order.objects.create(
    user=customer,
    restaurant=restaurant1,
    address=address1,
    total=90000,
    status='DELIVERED'
)
print("Đã tạo Order:", order)

# Tạo chi tiết đơn hàng
order_detail = OrderDetail.objects.create(
    order=order,
    food=food1,
    quantity=2,
    sub_total=90000,  # 2 * 45000 (giá buổi tối)
    time_serve='EVENING'
)
print("Đã tạo OrderDetail:", order_detail)

# Tạo thanh toán cho order
payment = Payment.objects.create(
    order=order,
    payment_method='Thẻ tín dụng',
    status='SUCCESS',
    total_payment=90000
)
print("Đã tạo Payment cho order:", payment)

# Tạo đánh giá nhà hàng
restaurant_review = RestaurantReview.objects.create(
    user=customer,
    restaurant=restaurant1,
    star=Decimal('4.8'),
    comment="Phở rất ngon, phục vụ nhanh!"
)
print("Đã tạo Restaurant Review:", restaurant_review)

# Tạo đánh giá món ăn
food_review1 = FoodReview.objects.create(
    user=customer,
    order_detail=order_detail,
    star=Decimal('4.5'),
    comment="Phở bò thơm, nước dùng đậm đà!"
)
print("Đã tạo Food Review 1:", food_review1)

# Cập nhật star_rating của món ăn
food1.update_star_rating()
print(f"Star rating của {food1.name} sau 1 đánh giá: {food1.star_rating} (Dự kiến: 4.5)")

# Tạo đơn hàng thứ hai
order2 = Order.objects.create(
    user=customer,
    restaurant=restaurant1,
    address=address1,
    total=40000,
    status='DELIVERED'
)
order_detail2 = OrderDetail.objects.create(
    order=order2,
    food=food1,
    quantity=1,
    sub_total=40000,  # Giá buổi sáng
    time_serve='MORNING'
)
payment2 = Payment.objects.create(
    order=order2,
    payment_method='Tiền mặt',
    status='SUCCESS',
    total_payment=40000
)
print("Đã tạo Payment cho order2:", payment2)
