from django.core.mail import send_mail
from django.conf import settings
from .models import Notification, User
import re
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

def is_valid_email(email):
    """
    Kiểm tra email có tồn tại và hợp lệ không
    """
    if not email or not isinstance(email, str):
        return False
        
    # Kiểm tra định dạng email cơ bản
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        return False
        
    try:
        validate_email(email)
        return True
    except ValidationError:
        return False

def send_notification_email(user_email, subject, message):
    """
    Gửi email thông báo
    """
    if not is_valid_email(user_email):
        print(f"Invalid email address: {user_email}")
        return False
        
    try:
        # Kiểm tra email có tồn tại trong database không
        if not User.objects.filter(email=user_email, is_active=True).exists():
            print(f"Email {user_email} not found in database")
            return False
            
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user_email],
            fail_silently=True
        )
        return True
    except Exception as e:
        print(f"Error sending email to {user_email}: {str(e)}")
        return False

def create_notification(user, notification_type, title, message, related_object_id=None, related_object_type=None):
    # Tạo thông báo trong database
    notification = Notification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title,
        message=message,
        related_object_id=related_object_id,
        related_object_type=related_object_type
    )
    
    # Chỉ gửi email nếu người dùng có email hợp lệ
    if user.email and '@' in user.email:
        send_notification_email(
            user.email,
            title,
            message
        )
    
    return notification

def notify_new_food(food):
    """
    Gửi thông báo cho khách hàng đã follow nhà hàng khi có món ăn mới
    """
    try:
        followers = food.restaurant.follows_as_restaurant.filter(status='FOLLOW').select_related('user')
        print(followers)
        
        notifications = []
        for follow in followers:
            notification = Notification.objects.create(
                user=follow.user,
                notification_type='new_food',
                title=f"Món ăn mới tại {food.restaurant.name}",
                message=food.name,
                related_object_id=food.id,
                related_object_type='food'
            )
            notifications.append(notification)
            
        if notifications:
            from firebase_admin import messaging
            fcm_tokens = [n.user.fcm_token for n in notifications if hasattr(n.user, 'fcm_token') and n.user.fcm_token]
            
            if fcm_tokens:
                message = messaging.MulticastMessage(
                    data={
                        'type': 'new_food',
                        'food_id': str(food.id),
                        'restaurant_id': str(food.restaurant.id)
                    },
                    notification=messaging.Notification(
                        title=f"Món ăn mới tại {food.restaurant.name}",
                        body=food.name
                    ),
                    tokens=fcm_tokens
                )
                messaging.send_multicast(message)
                
        return True
    except Exception as e:
        print(f"Error sending food notification: {str(e)}")
        return False

def notify_new_menu(menu):
    """
    Gửi thông báo cho khách hàng đã follow nhà hàng khi có menu mới
    """
    try:
        # Lấy danh sách khách hàng đã follow nhà hàng
        followers = menu.restaurant.follows_as_restaurant.filter(status='FOLLOW').select_related('user')
        
        # Tạo thông báo cho từng follower
        notifications = []
        for follow in followers:
            notification = Notification.objects.create(
                user=follow.user,
                notification_type='new_menu',
                title=f"Menu mới tại {menu.restaurant.name}",
                message=f"{menu.name} - {menu.description}",
                related_object_id=menu.id,
                related_object_type='menu'
            )
            notifications.append(notification)
            
        # Gửi thông báo qua FCM nếu có
        if notifications:
            from firebase_admin import messaging
            
            # Lấy FCM tokens của các user
            fcm_tokens = [n.user.fcm_token for n in notifications if hasattr(n.user, 'fcm_token') and n.user.fcm_token]
            
            if fcm_tokens:
                message = messaging.MulticastMessage(
                    data={
                        'type': 'new_menu',
                        'menu_id': str(menu.id),
                        'restaurant_id': str(menu.restaurant.id)
                    },
                    notification=messaging.Notification(
                        title=f"Menu mới tại {menu.restaurant.name}",
                        body=f"{menu.name} - {menu.description}"
                    ),
                    tokens=fcm_tokens
                )
                messaging.send_multicast(message)
                
        return True
    except Exception as e:
        print(f"Error sending menu notification: {str(e)}")
        return False 