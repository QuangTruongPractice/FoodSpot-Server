# File: test_models.py
# Lưu file này trong thư mục E:\BTLON\FoodSpot-Server\foodspotapp\foodspots\test_models.py
# Hướng dẫn chạy:
# 1. Mở terminal, di chuyển đến thư mục chứa manage.py: E:\BTLON\FoodSpot-Server\foodspotapp
# 2. Chạy lệnh: python manage.py shell
# 3. Trong shell, nhập: exec(open('foodspots/test_models.py', encoding='utf-8').read())

# Nhập các model cần thiết
from foodspots.models import User, Address, Restaurant, Follow

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
    fullname='Customer Name',
    username='customer1',
    role='CUSTOMER'
)
customer.addresses.add(address1, address2)  # Liên kết customer với cả hai địa chỉ
print("Đã tạo CUSTOMER:", customer.email)

# Tạo người dùng CUSTOMER thứ hai và liên kết với địa chỉ
customer2 = User.objects.create_user(
    email='customer2@example.com',
    password='password123',
    fullname='Customer Two',
    username='customer2',
    role='CUSTOMER'
)
customer2.addresses.add(address1)  # customer2 chia sẻ địa chỉ address1 với customer
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

# Tạo một nhà hàng với địa chỉ
restaurant = Restaurant.objects.create(
    name='Restaurant A',
    phone_number='1234567890',
    owner=restaurant_user,
    star_rating=4.5,
    address=restaurant_address  # Liên kết với địa chỉ
)
print("Đã tạo nhà hàng:", restaurant.name)

# Tạo mối quan hệ Follow
follow = Follow.objects.create(
    user=customer,
    restaurant=restaurant,
    status='FOLLOW'
)
print("Đã tạo mối quan hệ Follow:", follow)

# Thử tạo một Follow với người dùng không phải CUSTOMER
try:
    invalid_follow = Follow.objects.create(
        user=restaurant_user,
        restaurant=restaurant,
        status='FOLLOW'
    )
except ValueError as e:
    print("Lỗi khi tạo Follow với RESTAURANT_USER:", e)

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

# Kiểm tra danh sách nhà hàng mà customer theo dõi
print("\nDanh sách nhà hàng mà", customer.email, "theo dõi:")
followed_restaurants = customer.follows_as_user.all()  # Đổi từ follows thành follows_as_user
for follow in followed_restaurants:
    print(follow.restaurant.name, follow.status)

# Kiểm tra danh sách người dùng theo dõi restaurant
print("\nDanh sách người dùng theo dõi", restaurant.name, ":")
followers = restaurant.follows_as_restaurant.all()  # Đổi từ follows thành follows_as_restaurant
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