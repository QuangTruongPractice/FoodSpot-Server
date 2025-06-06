from rest_framework.serializers import ModelSerializer
from rest_framework.fields import SerializerMethodField
from .models import (Order, OrderDetail, Food, FoodCategory, FoodReview, RestaurantReview,
                     FoodPrice, Follow, Favorite, User, Address, Restaurant, Cart, SubCart,
                     SubCartItem, Menu, Notification)
from rest_framework import serializers
from cloudinary.uploader import upload
from collections import defaultdict
import re
from PIL import Image
import io, time
from django.core.files.base import ContentFile

class BaseSerializer(ModelSerializer):
    image = SerializerMethodField()

    def get_image(self, obj):
        """Trả về URL ảnh trực tiếp từ CloudinaryField"""
        if hasattr(obj, 'image') and obj.image:
            return str(obj.image)  # CloudinaryField lưu URL dưới dạng chuỗi
        return None

    def compress_image(self, image_file):
        """Nén ảnh và trả về dữ liệu bytes thay vì ContentFile"""
        img = Image.open(image_file)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        output = io.BytesIO()
        img.thumbnail((600, 600))  # Giảm kích thước để tối ưu
        img.save(output, format='JPEG', quality=75)  # Giảm chất lượng
        output.seek(0)
        # Trả về bytes trực tiếp thay vì ContentFile để tránh lỗi tuần tự hóa
        return output.getvalue()

    def create(self, validated_data):
        request = self.context.get('request')
        print(f"Request in serializer: {request}")
        print(f"Request FILES: {getattr(request, 'FILES', None) if request else None}")

        image_file = None
        if request and hasattr(request, 'FILES'):
            image_file = request.FILES.get('image')
            print(f"Image file found: {image_file}")

        if image_file:
            try:
                compressed_image = self.compress_image(image_file)
                upload_result = upload(compressed_image, resource_type="image")
                validated_data['image'] = upload_result['secure_url']
                print(f"Image uploaded successfully: {upload_result['secure_url']}")
            except Exception as e:
                print(f"Upload error: {str(e)}")
                raise serializers.ValidationError(f"Upload ảnh thất bại: {str(e)}")

        avatar_file = request.FILES.get('avatar')
        if avatar_file:
            compressed = self.compress_image(avatar_file)
            upload_result = upload(compressed, resource_type="image")
            validated_data['avatar'] = upload_result['secure_url']

        return super().create(validated_data)

    def update(self, instance, validated_data):
        request = self.context.get('request')
        image_file = None
        if request and hasattr(request, 'FILES'):
            image_file = request.FILES.get('image')

        if image_file:
            try:
                compressed_image = self.compress_image(image_file)
                upload_result = upload(compressed_image, resource_type="image")
                validated_data['image'] = upload_result['secure_url']
            except Exception as e:
                raise serializers.ValidationError(f"Upload ảnh thất bại: {str(e)}")
        elif 'image' in validated_data and validated_data['image'] == '':
            validated_data['image'] = None  # Xóa ảnh
        elif 'image' not in validated_data:
            validated_data['image'] = instance.image  # Giữ ảnh cũ

        return super().update(instance, validated_data)



class UserSerializer(BaseSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'phone_number',
                  'role', 'password', 'avatar', 'is_approved']
        extra_kwargs = {
            'password': {'write_only': True},
            'role': {'required': False},
            'phone_number': {'required': False},
        }

    def validate_email(self, value):
        if not value:
            raise serializers.ValidationError("Email is required")
        return value

    def validate_username(self, value):
        if not value:
            raise serializers.ValidationError("Username is required")
        return value

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.avatar:
            data['avatar'] = instance.avatar.url
        else:
            data['avatar'] = None
        return data

class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ['id', 'name', 'latitude', 'longitude']

class UserAddressSerializer(serializers.ModelSerializer):
    addresses = AddressSerializer(many=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'addresses']

class RestaurantSerializer(BaseSerializer):
    owner = UserSerializer(read_only=True)
    address = AddressSerializer()
    avatar = serializers.ImageField(allow_null=True, required=False)

    class Meta:
        model = Restaurant
        fields = ['id', 'name', 'avatar', 'phone_number', 'owner', 'star_rating', 'shipping_fee_per_km', 'address']

    def update(self, instance, validated_data):
        print("Validated data in serializer:", validated_data)  # Log để debug
        address_data = validated_data.pop('address', None)

        # Cập nhật các trường cơ bản
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Cập nhật Address
        if address_data and instance.address:
            address = instance.address
            for attr, value in address_data.items():
                setattr(address, attr, value)
            address.save()
        elif address_data and not instance.address:
            # Tạo mới Address nếu không tồn tại
            address = Address.objects.create(**address_data)
            instance.address = address

        instance.save()
        return instance

class RestaurantAddressSerializer(serializers.ModelSerializer):
    address = AddressSerializer()

    class Meta:
        model = Restaurant
        fields = ['id', 'name', 'address']

class MenuSerializer(BaseSerializer):
    foods = serializers.SerializerMethodField()
    restaurant = serializers.SlugRelatedField(slug_field='name', read_only=True)

    class Meta:
        model = Menu
        fields = ['id', 'restaurant', 'name', 'description', 'time_serve', 'foods', 'is_active']

    def get_foods(self, obj):
        time_serve = obj.time_serve
        # Lọc foods theo restaurant và time_serve
        queryset = obj.foods.filter(
            restaurant=obj.restaurant,
            prices__time_serve=time_serve
        ).distinct()

        serializer = FoodInMenuSerializer(queryset, many=True, context={'time_serve': time_serve})
        return serializer.data

class FoodInMenuSerializer(BaseSerializer):
    price = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()

    class Meta:
        model = Food
        fields = ['id', 'name', 'image', 'description', 'price', 'is_available']

    def get_price(self, obj):
        # Lấy time_serve từ context truyền vào
        time_serve = self.context.get('time_serve')
        price_obj = obj.prices.filter(time_serve=time_serve).first()
        return price_obj.price if price_obj else None

    def get_image(self, obj):
        return obj.image.url if obj.image else None

class FoodCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = FoodCategory
        fields = ['id', 'name']

class FoodPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = FoodPrice
        fields = ['time_serve', 'price']

class FoodSerializers(BaseSerializer):
    prices = FoodPriceSerializer(many=True, read_only=True)
    restaurant_name = serializers.CharField(source="restaurant.name", read_only=True)
    class Meta:
        model = Food
        fields = ["id", "name", "restaurant", "restaurant_name","image", "food_category",
                  "prices", "description", "is_available", "star_rating"]
        extra_kwargs = {
            'name': {'required': True},
            'restaurant': {'required': True},
            'food_category': {'required': True},
        }

    def to_internal_value(self, data):
        data = data.copy()
        prices = []
        # Tìm các trường prices[i][field]
        price_fields = defaultdict(dict)
        for key, value in data.items():
            match = re.match(r'prices\[(\d+)\]\[(\w+)\]', key)
            if match:
                index, field = match.groups()
                price_fields[int(index)][field] = value
        # Chuyển thành danh sách prices
        for index in sorted(price_fields.keys()):
            price = price_fields[index]
            if 'time_serve' in price and 'price' in price:
                prices.append({
                    'time_serve': price['time_serve'],
                    'price': int(price['price'])
                })
        if prices:
            data['prices'] = prices
        return super().to_internal_value(data)

    def validate(self, data):
        # Chỉ validate prices nếu có dữ liệu prices được gửi lên
        prices = data.get('prices')
        if prices is not None and len(prices) == 0:
            raise serializers.ValidationError({"prices": "Nếu gửi prices thì phải có ít nhất 1 giá."})
        return data

    def create(self, validated_data):
        prices_data = validated_data.pop('prices', [])


        food = super().create(validated_data)

        # Tạo prices
        for price_data in prices_data:
            FoodPrice.objects.create(food=food, **price_data)

        return food

    def update(self, instance, validated_data):
        prices_data = validated_data.pop('prices', None)

        # Cập nhật các trường khác trước
        instance = super().update(instance, validated_data)

        # Cập nhật prices nếu có
        if prices_data is not None:
            # Xóa tất cả prices cũ
            instance.prices.all().delete()
            # Tạo lại prices mới
            for price_data in prices_data:
                FoodPrice.objects.create(food=instance, **price_data)

        return instance

class OrderDetailSerializer(BaseSerializer):
    food = serializers.SerializerMethodField()
    class Meta:
        model = OrderDetail
        fields = ['id', 'food', 'order', 'time_serve','quantity', 'sub_total']

    def get_food(self, obj):
        food_data = FoodSerializers(obj.food).data  # Lấy thông tin đầy đủ món ăn
        # Lọc ra chỉ 1 price ứng với time_serve của OrderDetail hiện tại
        matched_price = next(
            (price for price in food_data['prices'] if price['time_serve'] == obj.time_serve),
            None
        )
        food_data['prices'] = [matched_price] if matched_price else []
        return food_data

class OrderSerializer(serializers.ModelSerializer):
    address = serializers.PrimaryKeyRelatedField(queryset=Address.objects.all())
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True)
    payment_method = serializers.CharField(source='payments.payment_method', read_only=True)
    payment_status = serializers.CharField(source='payments.status', read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'user', 'restaurant', 'restaurant_name', 'ordered_date', 'address',
                  'total', 'status', 'shipping_fee', 'payment_method', 'payment_status']
        extra_kwargs = {
            'user': {'read_only': True},
            'ordered_date': {'read_only': True},
        }

class FoodReviewSerializers(BaseSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    avatar = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField(required=False)
    class Meta:
        model = FoodReview
        fields = ['id', 'user', 'user_name', 'avatar', 'order_detail', 'comment', 'created_date', 'star', 'replies']

    def get_replies(self, obj):
        replies = FoodReview.objects.filter(parent=obj)
        return FoodReviewSerializers(replies, many=True).data

    def get_avatar(self, obj):
        return obj.user.avatar.url

class RestaurantReviewSerializer(BaseSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    avatar = serializers.SerializerMethodField()
    class Meta:
        model = RestaurantReview
        fields = ['id', 'user', 'user_name', 'avatar', 'restaurant', 'comment', 'created_date', 'star']

    def get_avatar(self, obj):
        return obj.user.avatar.url if obj.user.avatar else None

class FollowSerializer(serializers.ModelSerializer):
    class Meta:
        model = Follow
        fields = ['id', 'user', 'restaurant', 'status']

class FavoriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Favorite
        fields = ['id', 'user', 'food', 'status']

class SubCartItemSerializer(serializers.ModelSerializer):
    food = FoodSerializers()
    restaurant = serializers.StringRelatedField()

    class Meta:
        model = SubCartItem
        fields = ['id', 'food', 'restaurant', 'sub_cart', 'quantity', 'price']

class SubCartSerializer(serializers.ModelSerializer):
    sub_cart_items = SubCartItemSerializer(many=True, read_only=True)
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True)

    class Meta:
        model = SubCart
        fields = ['id', 'cart', 'restaurant', 'restaurant_name', 'total_price', 'total_quantity', 'sub_cart_items']

class CartSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    class Meta:
        model = Cart
        fields = ['id', 'user', 'item_number', 'total_price']

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'notification_type', 'title', 'message', 'is_read', 'created_at', 'related_object_id', 'related_object_type']
        read_only_fields = ['created_at']

# class MessageSerializer(serializers.ModelSerializer):
#     sender = UserSerializer(read_only=True)
#
#     class Meta:
#         model = Message
#         fields = ['id', 'sender', 'content', 'created_date', 'is_read']
#
#
# class ChatRoomSerializer(serializers.ModelSerializer):
#     user1 = UserSerializer(read_only=True)
#     user2 = UserSerializer(read_only=True)
#     latest_message = serializers.SerializerMethodField()
#
#     class Meta:
#         model = ChatRoom
#         fields = ['id', 'user1', 'user2', 'last_message', 'last_message_time', 'is_active', 'latest_message']
#
#     def get_latest_message(self, obj):
#         return obj.latest_message[0].content if obj.latest_message else None