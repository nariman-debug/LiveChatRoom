from django.db import models

# Create your models here.


from django.db import models
from django.contrib.auth.models import AbstractUser


class CustomUser(AbstractUser):
    online = models.BooleanField(default=False)

    class Meta:
        db_table = 'custom_user'  # اضافه کردن این خط


class Message(models.Model):
    user = models.ForeignKey('chatroom.CustomUser', on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}: {self.content[:20]}"