import uuid

import redis
from config import redis_users_settings, LIST_USERS_KEY

from pip._vendor import requests

client = redis.Redis(host='127.0.0.1', port=6379, db=24)
for i in range(1000000):
    user_id = str(uuid.uuid4())
    requests.post(url='http://localhost:6665/users', data={'name': user_id[:6]})

