from rest_framework import serializers
from cloudinary.uploader import upload
from rest_framework.serializers import ModelSerializer, SerializerMethodField
from .models import Order, OrderDetail, Food, FoodCategory, FoodReview, RestaurantReview, FoodPrice, Follow, Favorite, User, Address, Restaurant, SubCart, SubCartItem, Menu
from PIL import Image
import io
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

    def compress_image(image_file):
        img = Image.open(image_file)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        output = io.BytesIO()
        img.thumbnail((800, 800))  # Giảm kích thước ảnh
        img.save(output, format='JPEG', quality=85)  # Nén chất lượng
        output.seek(0)
        return ContentFile(output.read(), name=image_file.name)

    def update(self, instance, validated_data):
        request = self.context.get('request')
        image_file = None
        if request and hasattr(request, 'FILES'):
            image_file = request.FILES.get('image')

        if image_file:
            try:
                # Nén ảnh trước khi upload
                compressed_image = compress_image(image_file)
                start_time = time.time()
                upload_result = upload(compressed_image)
                end_time = time.time()
                print(f"Cloudinary upload time: {end_time - start_time} seconds")
                validated_data['image'] = upload_result['url']
            except Exception as e:
                raise serializers.ValidationError(f"Upload ảnh thất bại: {str(e)}")
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

class AddressSerializer(BaseSerializer):
    class Meta:
        model = Address
        fields = ['id', 'name', 'latitude', 'longitude']

class UserAddressSerializer(BaseSerializer):
    addresses = AddressSerializer(many=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'addresses']

class RestaurantSerializer(BaseSerializer):
    owner = UserSerializer(read_only=True)
    address = AddressSerializer()

    class Meta:
        model = Restaurant
        fields = ['id', 'name', 'avatar', 'phone_number', 'owner', 'star_rating', 'shipping_fee_per_km', 'address']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.avatar:
            data['avatar'] = instance.avatar.url
        else:
            data['avatar'] = None
        return data

class RestaurantAddressSerializer(BaseSerializer):
    address = AddressSerializer()

    class Meta:
        model = Restaurant
        fields = ['id', 'name', 'address']

class SubCartItemSerializer(BaseSerializer):
    food = serializers.SlugRelatedField(slug_field='name', read_only=True)
    restaurant = serializers.SlugRelatedField(slug_field='name', read_only=True)

    class Meta:
        model = SubCartItem
        fields = ['id', 'food', 'restaurant', 'quantity', 'price']

class SubCartSerializer(BaseSerializer):
    sub_cart_items = SubCartItemSerializer(many=True, read_only=True)
    restaurant = serializers.SlugRelatedField(slug_field='name', read_only=True)

    class Meta:
        model = SubCart
        fields = ['id', 'cart', 'restaurant', 'total_price', 'sub_cart_items']

class MenuSerializer(BaseSerializer):
    foods = serializers.SerializerMethodField()
    restaurant = serializers.SlugRelatedField(slug_field='name', read_only=True)

    class Meta:
        model = Menu
        fields = ['id', 'restaurant', 'name', 'description', 'time_serve', 'foods', 'is_active']

    def get_foods(self, obj):
        time_serve = obj.time_serve
        queryset = obj.foods.filter(
            restaurant=obj.restaurant,
            prices__time_serve=time_serve
        ).distinct()
        serializer = FoodInMenuSerializer(queryset, many=True, context={'time_serve': time_serve})
        return serializer.data

class FoodInMenuSerializer(BaseSerializer):
    price = serializers.SerializerMethodField()

    class Meta:
        model = Food
        fields = ['id', 'name', 'image', 'description', 'price']

    def get_price(self, obj):
        time_serve = self.context.get('time_serve')
        price_obj = obj.prices.filter(time_serve=time_serve).first()
        return price_obj.price if price_obj else None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.image:
            data['image'] = instance.image.url
        else:
            data['image'] = None
        return data

class FoodCategorySerializer(BaseSerializer):
    class Meta:
        model = FoodCategory
        fields = ['id', 'name']

class FoodPriceSerializer(BaseSerializer):
    class Meta:
        model = FoodPrice
        fields = ['time_serve', 'price']

class FoodSerializers(BaseSerializer):
    prices = FoodPriceSerializer(many=True, read_only=True)
    restaurant_name = serializers.CharField(source="restaurant.name", read_only=True)

    class Meta:
        model = Food
        fields = ["id", "name", "restaurant", "restaurant_name", "image", "food_category", "prices", "description"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.image:
            data['image'] = instance.image.url
        else:
            data['image'] = None
        return data

class OrderDetailSerializer(BaseSerializer):
    food = serializers.SerializerMethodField()

    class Meta:
        model = OrderDetail
        fields = ['id', 'food', 'order', 'time_serve', 'quantity', 'sub_total']

    def get_food(self, obj):
        food_data = FoodSerializers(obj.food).data
        matched_price = next(
            (price for price in food_data['prices'] if price['time_serve'] == obj.time_serve),
            None
        )
        food_data['prices'] = [matched_price] if matched_price else []
        return food_data

class OrderSerializer(BaseSerializer):
    address = serializers.PrimaryKeyRelatedField(queryset=Address.objects.all())

    class Meta:
        model = Order
        fields = ['id', 'user', 'restaurant', 'ordered_date', 'address', 'total', 'status']
        extra_kwargs = {
            'user': {'read_only': True},
            'ordered_date': {'read_only': True},
        }

class FoodReviewSerializers(BaseSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = FoodReview
        fields = ['id', 'user', 'user_name', 'order_detail', 'comment', 'created_date', 'star']

class RestaurantReviewSerializer(BaseSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True)

    class Meta:
        model = RestaurantReview
        fields = ['id', 'user', 'user_name', 'restaurant', 'restaurant_name', 'comment', 'created_date', 'star']

class FollowSerializer(BaseSerializer):
    class Meta:
        model = Follow
        fields = ['id', 'user', 'restaurant', 'status']

class FavoriteSerializer(BaseSerializer):
    class Meta:
        model = Favorite
        fields = ['id', 'user', 'food', 'status']