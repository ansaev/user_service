import uuid

import redis
from config import redis_users_settings, LIST_USERS_KEY

client = redis.Redis(host='127.0.0.1', port=6379, db=24)
for i in range(1000000):
    user_id = str(uuid.uuid4())
    client.set(name=user_id, value=user_id)
    client.lpush(LIST_USERS_KEY, user_id)

