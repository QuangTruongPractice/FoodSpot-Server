Backend Đặt Món Ăn (Django)

1) Giới thiệu
Backend viết bằng **Django REST Framework** cho ứng dụng đặt món ăn nhiều nhà hàng.  
Chức năng chính: đăng nhập, quản lý món ăn, đặt hàng, thanh toán, thống kê.

2) Chức năng chính
- Đăng nhập bằng OAuth2, phân quyền: Khách hàng, Nhà hàng, Quản trị viên.  
- Quản lý món ăn, danh mục, menu; tìm kiếm theo tên, nhà hàng, giá.  
- Đặt hàng từ nhà hàng, mô phỏng thanh toán bằng MoMo UAT.  
- Người dùng có thể có nhiều địa chỉ giao hàng.  
- Nhà hàng: quản lý menu, cập nhật thông tin, xem thống kê doanh thu theo tháng/quý/năm.  
- Admin: quản lý toàn hệ thống và thống kê qua Django Admin.  
- Người dùng: xem các đơn hàng đã đặt (thành công, thất bại, đang giao).  

3) Công nghệ
- Django, Django REST Framework  
- OAuth2 (django-oauth-toolkit)  
- MySQL / PostgreSQL  
- Thanh toán MoMo UAT  

4) Cài đặt
```bash
git clone https://github.com/your-repo/food-ordering-backend.git
cd food-ordering-backend

python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

pip install -r requirements.txt
-> Chỉnh lại database ở file settings
python manage.py makemigrations
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```
