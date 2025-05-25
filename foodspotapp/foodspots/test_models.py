# File: foodspots/test_models.py
# Hướng dẫn chạy:
# 1. Mở terminal, di chuyển đến thư mục chứa manage.py: E:\BTLON\FoodSpot-Server\foodspotapp
# 2. Chạy lệnh: python manage.py shell
# 3. Trong shell, nhập: exec(open('foodspots/test_models.py', encoding='utf-8').read())

# Nhập các model cần thiết
from foodspots.models import User, Address, Tag, Restaurant, Follow, Order, OrderDetail, Payment, FoodCategory, Food, FoodPrice, Menu, RestaurantReview, FoodReview, Cart, SubCart, SubCartItem
from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError

# Bước 1: Tạo dữ liệu test
print("=== Bắt đầu tạo dữ liệu test ===")

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
admin = User.objects.create_user(
    email='admin123@gmail.com',
    password='123',
    first_name='Nguyễn',
    last_name='Văn A',
    username='admin123',
    role='ADMIN'
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
restaurant_user1 = User.objects.create_user(
    email='chuquan1@example.com',
    password='matkhau123',
    first_name='Lê',
    last_name='Văn C',
    username='chuquan1',
    role='RESTAURANT_USER'
)
print("Đã tạo RESTAURANT_USER 1:", restaurant_user1.email)

# Tạo người dùng RESTAURANT_USER thứ hai (vì OneToOneField chỉ cho phép 1 nhà hàng mỗi user)
restaurant_user2 = User.objects.create_user(
    email='chuquan2@example.com',
    password='matkhau123',
    first_name='Phạm',
    last_name='Thị D',
    username='chuquan2',
    role='RESTAURANT_USER'
)
print("Đã tạo RESTAURANT_USER 2:", restaurant_user2.email)

# Tạo tag
tag1 = Tag.objects.create(name='Ẩm thực Việt')
tag2 = Tag.objects.create(name='Đồ uống')
print("Đã tạo Tag:", tag1, tag2)

# Tạo nhà hàng
restaurant1 = Restaurant.objects.create(
    name='Quán Phở Sài Gòn',
    phone_number='0909123456',
    owner=restaurant_user1,
    star_rating=4.7,
    address=restaurant_address1
)
restaurant1.tags.add(tag1)
restaurant2 = Restaurant.objects.create(
    name='Trà Sữa Nhà Làm',
    phone_number='0918234567',
    owner=restaurant_user2,  # Nhà hàng thứ hai cần owner khác
    star_rating=4.3,
    address=restaurant_address2
)
restaurant2.tags.add(tag2)
print("Đã tạo nhà hàng:", restaurant1.name, restaurant2.name)

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
food_review2 = FoodReview.objects.create(
    user=customer,
    order_detail=order_detail2,
    star=Decimal('5.0'),
    comment="Phở sáng ngon tuyệt!"
)
print("Đã tạo Food Review 2:", food_review2)

# Cập nhật star_rating
food1.update_star_rating()
print(f"Star rating của {food1.name} sau 2 đánh giá: {food1.star_rating} (Dự kiến: (4.5 + 5.0) / 2 = 4.75)")

# Tạo reply từ restaurant_user
food_review_reply = FoodReview.objects.create(
    user=restaurant_user1,  # Dùng restaurant_user1 (chủ của restaurant1)
    order_detail=order_detail,
    comment="Cảm ơn bạn đã yêu thích phở của quán!",
    star=Decimal('0.0'),
    parent=food_review1
)
print("Đã tạo Food Review Reply:", food_review_reply)

# Kiểm tra star_rating sau reply
food1.update_star_rating()
print(f"Star rating của {food1.name} sau reply: {food1.star_rating} (Dự kiến: vẫn 4.75)")



# # Thử tạo reply với star
# try:
#     invalid_food_review_reply_star = FoodReview.objects.create(
#         user=restaurant_user1,
#         comment="Cảm ơn bạn!",
#         star=Decimal('3.0'),  # Để kiểm tra lỗi star
#         parent=food_review1
#     )
# except (ValidationError, ValueError) as e:
#     print("Lỗi khi tạo Food Review Reply với star:", str(e))

# # Thử tạo đánh giá nhà hàng từ customer2 (không có đơn hàng)
# try:
#     invalid_restaurant_review = RestaurantReview.objects.create(
#         user=customer2,
#         restaurant=restaurant1,
#         star=Decimal('3.5'),
#         comment="Quán cũng được"
#     )
# except ValueError as e:
#     print("Lỗi khi tạo Restaurant Review từ", customer2.email, ":", e)




# Bước 2: Truy vấn và kiểm tra dữ liệu
print("\n=== Kiểm tra dữ liệu ===")

# Kiểm tra địa chỉ của customer
print("\nDanh sách địa chỉ của", customer.email, ":")
for address in customer.addresses.all():
    print(address.name, address.latitude, address.longitude)

# Kiểm tra người dùng sử dụng address1
print("\nDanh sách người dùng sử dụng", address1.name, ":")
for user in address1.users.all():
    print(user.email)

# Kiểm tra tag của restaurant1
print("\nDanh sách tag của", restaurant1.name, ":")
for tag in restaurant1.tags.all():
    print(tag.name)

# Kiểm tra địa chỉ của nhà hàng
print("\nĐịa chỉ của", restaurant1.name, ":")
if restaurant1.address:
    print(restaurant1.address.name, restaurant1.address.latitude, restaurant1.address.longitude)

# Kiểm tra món ăn trong menu
print("\nDanh sách món ăn trong", menu1.name, ":")
for food in menu1.foods.all():
    prices = food.prices.all()
    for price in prices:
        print(f"{food.name} ({price.time_serve}): {price.price}")

# Kiểm tra menu của restaurant
print("\nDanh sách menu của", restaurant1.name, ":")
for menu in restaurant1.menus.all():
    print(menu.name, menu.time_serve)

# Kiểm tra giỏ hàng
print("\nDanh sách giỏ hàng của", customer.email, ":")
print(cart, cart.item_number)

# Kiểm tra SubCart
print("\nDanh sách SubCart của", cart, ":")
for sub_cart in cart.sub_carts.all():
    print(sub_cart, sub_cart.total_price)

# Kiểm tra SubCartItem
print("\nDanh sách SubCartItem của", sub_cart1, ":")
for item in sub_cart1.sub_cart_items.all():
    print(item, item.quantity, item.price, item.time_serve)

# Kiểm tra đơn hàng
print("\nDanh sách đơn hàng của", customer.email, ":")
for order in customer.orders.all():
    print(order, order.total, order.status)

# Kiểm tra chi tiết đơn hàng
print("\nDanh sách chi tiết đơn hàng của", order, ":")
for detail in order.order_details.all():
    print(detail, detail.quantity, detail.sub_total, detail.time_serve)

# Kiểm tra đánh giá món ăn
print("\nDanh sách đánh giá món ăn trong", order_detail, ":")
for review in order_detail.order_food_reviews.all():
    print(review, review.comment)
    for reply in review.replies.all():
        print(f"  Reply: {reply}, {reply.comment}")

# Kiểm tra thanh toán của order
print("\nDanh sách thanh toán của", order, ":")
try:
    payment = order.payments
    print(payment, payment.payment_method, payment.status)
except Payment.DoesNotExist:
    print("Đơn hàng này chưa có thanh toán.")

# Kiểm tra thanh toán của order2
print("\nDanh sách thanh toán của", order2, ":")
try:
    payment2 = order2.payments
    print(payment2, payment2.payment_method, payment2.status)
except Payment.DoesNotExist:
    print("Đơn hàng này chưa có thanh toán.")

# Kiểm tra đánh giá nhà hàng
print("\nDanh sách đánh giá nhà hàng của", restaurant1.name, ":")
for review in restaurant1.restaurant_reviews.all():
    print(review, review.comment)

# Kiểm tra nhà hàng được theo dõi
print("\nDanh sách nhà hàng mà", customer.email, "theo dõi:")
for follow in customer.follows_as_user.all():
    print(follow.restaurant.name, follow.status)

# Kiểm tra nhà hàng của restaurant_user1
print("\nNhà hàng của", restaurant_user1.email, ":")
if hasattr(restaurant_user1, 'restaurant'):
    print(restaurant_user1.restaurant.name)
else:
    print("Chưa có nhà hàng.")

# Kiểm tra nhà hàng của restaurant_user2
print("\nNhà hàng của", restaurant_user2.email, ":")
if hasattr(restaurant_user2, 'restaurant'):
    print(restaurant_user2.restaurant.name)
else:
    print("Chưa có nhà hàng.")

print("\n=== Kết thúc test ===")
