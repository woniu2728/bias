from apps.users.models import User
from django.contrib.auth.hashers import make_password

# 创建管理员账号
admin = User.objects.create(
    username='admin',
    email='admin@bias.local',
    password=make_password('admin123'),
    is_staff=True,
    is_superuser=True,
    is_email_confirmed=True,
    display_name='Administrator'
)

print(f"Admin account created successfully!")
print(f"Username: {admin.username}")
print(f"Email: {admin.email}")
print(f"Password: admin123")
print(f"ID: {admin.id}")
