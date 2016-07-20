import logging
from json import loads, dumps
from uuid import uuid4
import tornadoredis
from config import redis_users_settings
from tornado.gen import coroutine, Task
from tornado.web import Application, RequestHandler


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
        users = yield Task(self.redis_users.keys, pattern='*')
        self.write(dumps(users))
        self.finish()

    @coroutine
    def post(self):
        # create user and return id
        try:
            name = str(self.get_body_argument('name'))
        except BaseException as encode_name_exep:
            self.set_status(status_code=400, reason='bad charecters in name: ' + str(encode_name_exep))
            self.finish()
            logging.error(str(encode_name_exep))
            return
        try:
            user_id = str(uuid4())
            resp = yield Task(self.redis_users.set, key=user_id, value=name)
            self.write(dumps({'id': user_id, 'name': name}))
        except BaseException as ecnode_uuid_exep:
            self.set_status(status_code=500, reason='internal error')
            self.finish()
            logging.critical(msg=str(ecnode_uuid_exep))
            return
        self.finish()
        return


class SearchUserById(BaseUserHandler):

    @coroutine
    def get(self, user_id):
        # get info about simmillar id
        user_id = str(user_id)
        users = yield Task(self.redis_users.keys, pattern='*' + user_id + '*')
        self.write(dumps(users))
        self.finish()


class SearchUserByName(BaseUserHandler):

    @coroutine
    def get(self, name):
        # get info about simmillar names
        self.write(name)
        self.finish()


def make_app():
    return Application([
        (r"/users/([a-zA-Z0-9-]+)", UserInfoHandler),
        (r"/users", UsersInfoHandler),
        (r"/search_user_by_id/([a-zA-Z0-9-]+)", SearchUserById),
        (r"/search_user_by_name/(.+)", SearchUserByName)
    ])