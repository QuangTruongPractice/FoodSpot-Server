from rest_framework import serializers
from .models import User, Address, Restaurant, SubCart, SubCartItem, Menu

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'phone_number', 'role']

class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ['id', 'name', 'latitude', 'longitude']

class UserAddressSerializer(serializers.ModelSerializer):
    addresses = AddressSerializer(many=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'addresses']

class RestaurantSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    address = AddressSerializer()

    class Meta:
        model = Restaurant
        fields = ['id', 'name', 'phone_number', 'owner', 'star_rating', 'address']

class RestaurantAddressSerializer(serializers.ModelSerializer):
    address = AddressSerializer()

    class Meta:
        model = Restaurant
        fields = ['id', 'name', 'address']

class SubCartItemSerializer(serializers.ModelSerializer):
    food = serializers.StringRelatedField()  # Hiển thị tên món ăn
    restaurant = serializers.StringRelatedField()  # Hiển thị tên nhà hàng

    class Meta:
        model = SubCartItem
        fields = ['id', 'food', 'restaurant', 'quantity', 'price']

class SubCartSerializer(serializers.ModelSerializer):
    sub_cart_items = SubCartItemSerializer(many=True, read_only=True)
    restaurant = serializers.StringRelatedField()  # Hiển thị tên nhà hàng

    class Meta:
        model = SubCart
        fields = ['id', 'cart', 'restaurant', 'total_price', 'sub_cart_items']

class MenuSerializer(serializers.ModelSerializer):
    foods = serializers.StringRelatedField(many=True)  # Hiển thị tên các món ăn
    restaurant = serializers.StringRelatedField()  # Hiển thị tên nhà hàng

    class Meta:
        model = Menu
        fields = ['id', 'restaurant', 'name', 'description', 'time_serve', 'foods', 'is_active']