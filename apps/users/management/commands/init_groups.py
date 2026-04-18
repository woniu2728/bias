"""
创建初始数据：默认用户组和权限
"""
from django.core.management.base import BaseCommand
from apps.users.models import Group, Permission


class Command(BaseCommand):
    help = '创建默认用户组和权限'

    def handle(self, *args, **options):
        self.stdout.write('开始创建默认用户组和权限...')

        # 创建用户组
        groups_data = [
            {
                'id': 1,
                'name': 'Admin',
                'name_singular': 'Admin',
                'name_plural': 'Admins',
                'color': '#B72A2A',
                'icon': 'fas fa-user-shield',
                'is_hidden': False,
            },
            {
                'id': 2,
                'name': 'Guest',
                'name_singular': 'Guest',
                'name_plural': 'Guests',
                'color': '',
                'icon': '',
                'is_hidden': False,
            },
            {
                'id': 3,
                'name': 'Member',
                'name_singular': 'Member',
                'name_plural': 'Members',
                'color': '',
                'icon': '',
                'is_hidden': False,
            },
            {
                'id': 4,
                'name': 'Moderator',
                'name_singular': 'Moderator',
                'name_plural': 'Moderators',
                'color': '#80349E',
                'icon': 'fas fa-shield-alt',
                'is_hidden': False,
            },
        ]

        for group_data in groups_data:
            group, created = Group.objects.get_or_create(
                id=group_data['id'],
                defaults=group_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'[OK] 创建用户组: {group.name}'))
            else:
                updates = []
                if not group.icon and group_data.get('icon'):
                    group.icon = group_data['icon']
                    updates.append('icon')
                if updates:
                    group.save(update_fields=updates)
                self.stdout.write(f'  用户组已存在: {group.name}')

        # Admin权限
        admin_permissions = [
            'viewForum',
            'startDiscussion',
            'discussion.reply',
            'discussion.edit',
            'discussion.delete',
            'discussion.hide',
            'discussion.rename',
            'discussion.lock',
            'discussion.sticky',
            'user.edit',
            'user.suspend',
            'viewUserList',
            'searchUsers',
        ]

        admin_group = Group.objects.get(id=1)
        for perm in admin_permissions:
            permission, created = Permission.objects.get_or_create(
                group=admin_group,
                permission=perm
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'[OK] 创建Admin权限: {perm}'))

        # Member权限
        member_permissions = [
            'viewForum',
            'startDiscussion',
            'discussion.reply',
            'discussion.editOwn',
            'discussion.deleteOwn',
            'viewUserList',
            'searchUsers',
        ]

        member_group = Group.objects.get(id=3)
        for perm in member_permissions:
            permission, created = Permission.objects.get_or_create(
                group=member_group,
                permission=perm
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'[OK] 创建Member权限: {perm}'))

        # Guest权限
        guest_permissions = [
            'viewForum',
        ]

        guest_group = Group.objects.get(id=2)
        for perm in guest_permissions:
            permission, created = Permission.objects.get_or_create(
                group=guest_group,
                permission=perm
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'[OK] 创建Guest权限: {perm}'))

        self.stdout.write(self.style.SUCCESS('\n[SUCCESS] 默认用户组和权限创建完成！'))
