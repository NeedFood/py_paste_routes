#!/paste_routes/bin/python
from paste.deploy import loadapp
import os
from wsgiref.simple_server import make_server


config = "python_paste.ini"
appname = "common"
wsgi_app = loadapp("config:%s" % os.path.abspath(config), appname)
server = make_server('localhost', 5000, wsgi_app)
server.serve_forever()
