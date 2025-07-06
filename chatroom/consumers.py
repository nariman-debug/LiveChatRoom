import json
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from .models import Message

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = "general"
        self.room_group_name = f'chat_{self.room_name}'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'user'):
            await self.notify_user_status(self.user.username, False)  # اطلاع به گروه‌ها
            await self.set_user_online_status(self.user, False)  # به‌روز کردن دیتابیس
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            action = data.get('action')

            if action == 'login':
                await self.handle_login(data)
            elif action == 'signup':
                await self.handle_signup(data)
            elif action == 'message':
                await self.handle_message(data)
            elif action == 'get_users':
                await self.send_users_list()
        except Exception as e:
            print(f"Error in receive: {str(e)}")
            await self.send_error_message(str(e))

    async def handle_login(self, data):
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()

        if not username or not password:
            return await self.send_auth_error('Username and password are required')

        try:
            user = await self.get_user_by_username(username)
            if not user:
                return await self.send_auth_error('User not found')

            is_valid = await self.verify_user_password(user, password)
            if not is_valid:
                return await self.send_auth_error('Invalid password')

            await self.set_user_online_status(user, True)
            self.user = user

            messages = await self.get_recent_messages()

            await self.send(json.dumps({
                'action': 'authenticated',
                'username': user.username,
                'messages': [
                    {
                        'user': msg.user.username,
                        'content': msg.content,
                        'time': msg.timestamp.strftime("%H:%M")
                    } for msg in messages
                ]
            }))

            await self.notify_user_status(user.username, True)

        except Exception as e:
            await self.send_auth_error(f'Login error: {str(e)}')

    async def handle_signup(self, data):
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()

        if not username or not password:
            return await self.send_auth_error('Username and password are required')

        try:
            existing_user = await self.get_user_by_username(username)
            if existing_user:
                return await self.send_auth_error('Username already exists')

            user = await self.create_new_user(username, password)
            await self.set_user_online_status(user, True)
            self.user = user

            await self.send(json.dumps({
                'action': 'authenticated',
                'username': user.username,
                'messages': []
            }))

            await self.notify_user_status(user.username, True)

        except Exception as e:
            await self.send_auth_error(f'Registration error: {str(e)}')

    async def handle_message(self, data):
        if not hasattr(self, 'user'):
            return

        message = data.get('message', '').strip()
        if not message:
            return

        try:
            msg = await self.save_message(self.user, message)

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'content': message,
                    'user': self.user.username,
                    'time': msg.timestamp.strftime("%H:%M")
                }
            )
        except Exception as e:
            print(f"Error saving message: {str(e)}")
            await self.send_error_message('Failed to send message')

    async def send_users_list(self):
        try:
            online_users = await self.get_online_users()
            await self.send(json.dumps({
                'action': 'users_list',
                'users': online_users
            }))
        except Exception as e:
            print(f"Error getting users list: {str(e)}")
            await self.send_error_message('Failed to get users list')

    # Database operations
    @database_sync_to_async
    def get_user_by_username(self, username):
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            return None

    @database_sync_to_async
    def verify_user_password(self, user, password):
        return user.check_password(password)

    @database_sync_to_async
    def create_new_user(self, username, password):
        return User.objects.create_user(username=username, password=password)

    @database_sync_to_async
    def save_message(self, user, content):
        return Message.objects.create(user=user, content=content)

    @database_sync_to_async
    def get_recent_messages(self):
        messages = Message.objects.select_related('user').order_by('-timestamp')[:50]
        return list(messages)

    @database_sync_to_async
    def get_online_users(self):
        return list(User.objects.filter(online=True).values_list('username', flat=True))

    @database_sync_to_async
    def set_user_online_status(self, user, status):
        user.online = status
        user.save()

    # Helper methods
    async def send_auth_error(self, message):
        await self.send(json.dumps({
            'action': 'auth_error',
            'message': message
        }))

    async def send_error_message(self, message):
        await self.send(json.dumps({
            'action': 'error',
            'message': message
        }))

    async def notify_user_status(self, username, online):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_status',
                'user': username,
                'online': online
            }
        )

    # Event handlers
    async def chat_message(self, event):
        await self.send(json.dumps({
            'action': 'message',
            'user': event['user'],
            'message': event['message'],
            'time': event['time']
        }))

    async def user_status(self, event):
        await self.send(json.dumps({
            'action': 'user_status',
            'user': event['user'],
            'online': event['online']
        }))