from django.core.management.base import BaseCommand
from apps.users.models import User
from django.contrib.auth.hashers import make_password


class Command(BaseCommand):
    help = 'Create admin user'

    def handle(self, *args, **options):
        # 检查是否已存在
        if User.objects.filter(username='admin').exists():
            self.stdout.write(self.style.WARNING('Admin user already exists!'))
            admin = User.objects.get(username='admin')
        else:
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
            self.stdout.write(self.style.SUCCESS('Admin user created successfully!'))

        self.stdout.write('=' * 50)
        self.stdout.write(f'Username: {admin.username}')
        self.stdout.write(f'Email: {admin.email}')
        self.stdout.write(f'Password: admin123')
        self.stdout.write(f'ID: {admin.id}')
        self.stdout.write('=' * 50)
