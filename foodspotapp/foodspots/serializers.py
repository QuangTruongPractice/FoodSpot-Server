from rest_framework.serializers import ModelSerializer
from rest_framework.fields import SerializerMethodField
from .models import (Order, OrderDetail, Food, FoodCategory, FoodReview, RestaurantReview,
                     FoodPrice, Follow, Favorite, User, Address, Restaurant, Cart, SubCart, SubCartItem, Menu)
from rest_framework import serializers
from cloudinary.uploader import upload
from PIL import Image
import io, time
from django.core.files.base import ContentFile

class BaseSerializer(ModelSerializer):
    image = SerializerMethodField()

    def get_image(self, obj):
        if hasattr(obj, 'image') and obj.image:
            return obj.image.url
        return None

    def create(self, validated_data):
        request = self.context.get('request')
        image_file = None
        if request and hasattr(request, 'FILES'):
            image_file = request.FILES.get('image')

        if image_file:
            try:
                upload_result = upload(image_file)
                validated_data['image'] = upload_result['url']
            except Exception as e:
                raise serializers.ValidationError(f"Upload ảnh thất bại: {str(e)}")
        return super().create(validated_data)

    def update(self, instance, validated_data):
        request = self.context.get('request')
        image_file = None
        if request and hasattr(request, 'FILES'):
            image_file = request.FILES.get('image')

        if image_file:
            try:
                # Nén ảnh trước khi upload
                compressed_image = self.compress_image(image_file)
                start_time = time.time()
                upload_result = upload(compressed_image)
                end_time = time.time()
                print(f"Cloudinary upload time: {end_time - start_time} seconds")
                validated_data['image'] = upload_result['url']
            except Exception as e:
                raise serializers.ValidationError(f"Upload ảnh thất bại: {str(e)}")
        return super().update(instance, validated_data)

    def compress_image(image_file):
        img = Image.open(image_file)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        output = io.BytesIO()
        img.thumbnail((800, 800))  # Giảm kích thước ảnh
        img.save(output, format='JPEG', quality=85)  # Nén chất lượng
        output.seek(0)
        return ContentFile(output.read(), name=image_file.name)

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

    def validate_name(self, value):
        if not value:
            raise serializers.ValidationError("Tên món ăn là bắt buộc")
        return value

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
        return obj.user.avatar.url if obj.user.avatar else None

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