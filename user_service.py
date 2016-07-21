import logging
from json import dumps
from uuid import uuid4
from math import ceil
import time
import tornadoredis
from tornadoredis.exceptions import ResponseError
from config import redis_users_settings, LIST_USERS_KEY, TRANSACTION_ATTEMPTS, SEARCHES_DB, NAMES_DB, SEARCH_LIVE_TIME, USERS_DB
from tornado.gen import coroutine, Task
from tornado.web import Application, RequestHandler
SEARCH_BY_ID = """
redis.call('select', ARGV[4])
local users = redis.call('keys', ARGV[1])
redis.call('select', ARGV[2] )
for i = 0, #users do
    redis.call('lpush', ARGV[3] , users[i])
end
return #users
"""


class BaseUserHandler(RequestHandler):
    @coroutine
    def prepare(self):
        self.redis_users = tornadoredis.Client(**redis_users_settings)
        self.redis_users.connect()

    @coroutine
    def on_finish(self):
        yield Task(self.redis_users.disconnect)

    def data_received(self, chunk):
        pass



class UserInfoHandler(BaseUserHandler):
    @coroutine
    def get(self, user_id):
        # get info about user
        redis_resp = yield Task(self.redis_users.get, key=user_id)
        if redis_resp is None:
            self.set_status(status_code=404, reason='no user with such user_id')
            self.finish()
            return
        result = {}
        self.finish()
        return

    @coroutine
    def post(self, user_id):
        # update name of user witth user_id
        pass

    def delete(self, user_id):
        # delete user with id
        pass


class UsersInfoHandler(BaseUserHandler):

    @coroutine
    def get(self):
        # get list of users
        try:
            page = int(self.get_argument('page'))
        except ValueError:
            self.set_status(status_code=400, reason='page should be int')
            self.finish()
            return
        try:
            limit = int(self.get_argument('limit'))
        except ValueError:
            self.set_status(status_code=400, reason='limit should be int')
            self.finish()
            return
        if limit < 1:
            self.set_status(status_code=400, reason='limit should be > 0')
            self.finish()
            return
        if page < 1:
            self.set_status(status_code=400, reason='page should be > 0')
            self.finish()
            return
        yield Task(self.redis_users.select, SEARCHES_DB)
        users_num = yield Task(self.redis_users.llen, LIST_USERS_KEY)
        pages = ceil(float(users_num)/float(limit))
        if page > pages:
            self.set_status(status_code=400, reason='page should be <= %d' % pages)
            self.finish()
            return
        start_index = page * limit
        end_index = start_index + limit
        users = yield Task(self.redis_users.lrange, key=LIST_USERS_KEY, start=start_index, end=end_index)
        self.write(dumps(users))
        self.finish()
        return

    @coroutine
    def post(self):
        #create user and return id
        try:
            name = str(self.get_body_argument('name'))
        except BaseException as encode_name_exep:
            self.set_status(status_code=400, reason='bad charecters in name: ' + str(encode_name_exep))
            self.finish()
            logging.error(str(encode_name_exep))
            return
        try:
            user_id = str(uuid4())
            pipe = self.redis_users.pipeline(transactional=True)
            pipe.select(USERS_DB)
            pipe.set(key=user_id, value=name)
            pipe.select(SEARCHES_DB)
            pipe.lpush(LIST_USERS_KEY, user_id)
            pipe.select(NAMES_DB)
            pipe.lpush(name, user_id)
            errors = []
            for i in range(TRANSACTION_ATTEMPTS):
                try:
                    resp_s, resp_p, err_1, err_2, err_2, err_3 = yield Task(pipe.execute)
                    break
                except BaseException as e:
                    errors.append(e)
                    continue
            else:
                self.set_status(status_code=500, reason='internal error')
                self.finish()
                msg = [str(e) for e in errors]
                msg = ';'.join(msg)
                logging.critical(msg='add new user transaction execution: ' + msg)
                return
            self.write(dumps({'id': user_id, 'name': name}))
        except BaseException as ecnode_uuid_exep:
            self.set_status(status_code=500, reason='internal error')
            self.finish()
            logging.critical(msg=str(ecnode_uuid_exep))
            return
        self.finish()
        return

def sleep(callback):
    time.sleep(2)
    if callable(callback):
        callback('ok')

class SearchUserById(BaseUserHandler):

    @coroutine
    def get(self):
        # get info about simmillar id
        try:
            page = int(self.get_argument('page'))
        except ValueError:
            self.set_status(status_code=400, reason='page should be int')
            self.finish()
            return
        try:
            limit = int(self.get_argument('limit'))
        except ValueError:
            self.set_status(status_code=400, reason='limit should be int')
            self.finish()
            return
        if limit < 1:
            self.set_status(status_code=400, reason='limit should be > 0')
            self.finish()
            return
        if page < 0:
            self.set_status(status_code=400, reason='page should be >= 0')
            self.finish()
            return
        user_id = self.get_argument('user_id')
        user_id = '*' + str(user_id) + '*'
        search_id = str(uuid4())
        users_num = yield Task(self.redis_users.eval, SEARCH_BY_ID, [0], [user_id, SEARCHES_DB, search_id, USERS_DB])
        pages = ceil(float(users_num)/float(limit))
        if page > pages:
            self.set_status(status_code=400, reason='page should be <= %d' % pages)
            self.finish()
            return
        start_index = page * limit
        end_index = start_index + limit
        yield Task(self.redis_users.select, SEARCHES_DB)
        for i in range(TRANSACTION_ATTEMPTS):
            users = yield Task(self.redis_users.lrange, key=search_id, start=start_index, end=end_index)
            if not isinstance(users, ResponseError):
                break
            else:
                yield Task(sleep)
        else:
            self.set_status(status_code=500, reason='cannot get data')
            self.finish()
            return
        self.write(dumps(users))
        self.finish()


class SearchUserByName(BaseUserHandler):
    @coroutine
    def prepare(self):
        self.redis_users = tornadoredis.Client(selected_db=NAMES_DB)
        self.redis_users.connect()

    @coroutine
    def get(self):
        # get info about simmillar names
        # check input params
        try:
            page = int(self.get_argument('page'))
        except ValueError:
            self.set_status(status_code=400, reason='page should be int')
            self.finish()
            return
        try:
            limit = int(self.get_argument('limit'))
        except ValueError:
            self.set_status(status_code=400, reason='limit should be int')
            self.finish()
            return
        if limit < 1:
            self.set_status(status_code=400, reason='limit should be > 0')
            self.finish()
            return
        if page < 0:
            self.set_status(status_code=400, reason='page should be >= 0')
            self.finish()
            return
        # it's a new search, run lua script
        name = self.get_argument('name')
        name = '*' + str(name) + '*'
        search_id = str(uuid4())
        users_num = yield Task(self.redis_users.eval, SEARCH_BY_ID, [name, SEARCHES_DB, search_id, NAMES_DB])
        print('users_num', users_num)
        pages = ceil(float(users_num)/float(limit))
        if page > pages:
            self.set_status(status_code=400, reason='page should be <= %d' % pages)
            self.finish()
            return
        start_index = page * limit
        end_index = start_index + limit
        yield Task(self.redis_users.select, SEARCHES_DB)
        for i in range(TRANSACTION_ATTEMPTS):
            users = yield Task(self.redis_users.lrange, key=search_id, start=start_index, end=end_index)
            if not isinstance(users, ResponseError):
                break
            else:
                yield Task(sleep)
        else:
            self.set_status(status_code=500, reason='cannot get data')
            self.finish()
            return
        result = {'limit': limit, 'page': page, 'pages': pages, 'search_id': search_id, 'data': users}
        self.write(dumps(result))
        self.finish()


def make_app():
    return Application([
        (r"/users/([a-zA-Z0-9-]+)", UserInfoHandler),
        (r"/users", UsersInfoHandler),
        (r"/search_user_by_id", SearchUserById),
        (r"/search_user_by_name", SearchUserByName)
    ])