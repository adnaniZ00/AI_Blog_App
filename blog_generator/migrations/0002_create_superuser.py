from django.db import migrations
import os

def create_superuser(apps, schema_editor):
    User = apps.get_model('auth', 'User')

    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'defaultpassword')
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@example.com')

    if not User.objects.filter(username=ADMIN_USERNAME).exists():
        User.objects.create_superuser(
            username=ADMIN_USERNAME,
            email=ADMIN_EMAIL,
            password=ADMIN_PASSWORD
        )
        print(f"Superuser '{ADMIN_USERNAME}' created.")
    else:
        print(f"Superuser '{ADMIN_USERNAME}' already exists.")


class Migration(migrations.Migration):

    dependencies = [
        ('blog_generator', '0001_initial'), # Make sure this matches your previous migration file
    ]

    operations = [
        migrations.RunPython(create_superuser),
    ]