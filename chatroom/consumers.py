import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from .models import Message, CustomUser
from django.contrib.auth import get_user_model

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
        if hasattr(self, 'user') and self.user.is_authenticated:
            await sync_to_async(self.user.update)(online=False)

        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
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

    async def handle_login(self, data):
        username = data['username']
        password = data['password']

        user = await sync_to_async(User.objects.filter)(username=username)
        user = await sync_to_async(user.first)()

        if user and user.check_password(password):
            self.user = user
            await sync_to_async(user.update)(online=True)

            # Send last 50 messages
            messages = await sync_to_async(list)(
                Message.objects.order_by('-timestamp')[:50]
            )
            messages.reverse()

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

            # Notify all users about new online user
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_status',
                    'user': user.username,
                    'online': True
                }
            )
        else:
            await self.send(json.dumps({
                'action': 'auth_error',
                'message': 'Invalid credentials'
            }))

    async def handle_signup(self, data):
        username = data['username']
        password = data['password']

        if await sync_to_async(User.objects.filter)(username=username).exists():
            await self.send(json.dumps({
                'action': 'auth_error',
                'message': 'Username already exists'
            }))
            return

        user = await sync_to_async(User.objects.create_user)(
            username=username,
            password=password
        )
        self.user = user
        await sync_to_async(user.update)(online=True)

        await self.send(json.dumps({
            'action': 'authenticated',
            'username': user.username,
            'messages': []
        }))

        # Notify all users about new user
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_status',
                'user': user.username,
                'online': True
            }
        )

    async def handle_message(self, data):
        if not hasattr(self, 'user') or not self.user.is_authenticated:
            return

        message = data['message']
        msg = await sync_to_async(Message.objects.create)(
            user=self.user,
            content=message
        )

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'user': self.user.username,
                'time': msg.timestamp.strftime("%H:%M")
            }
        )

    async def send_users_list(self):
        online_users = await sync_to_async(list)(
            User.objects.filter(online=True).values_list('username', flat=True)
        )
        await self.send(json.dumps({
            'action': 'users_list',
            'users': online_users
        }))

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