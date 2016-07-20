from sys import argv
from tornado.ioloop import IOLoop
from user_service import make_app

if __name__=='__main__':
    port = None
    for arg_id in range(1, len(argv) -1):
        if str(argv[arg_id]) == '-p':
            try:
                port = int(argv[arg_id+1])
            except BaseException:
                pass
            break
    if isinstance(port, int):
        loop = IOLoop.current()
        app = make_app()
        app.listen(port=port)
        loop.start()
    else:
        print('failed to get port from param')