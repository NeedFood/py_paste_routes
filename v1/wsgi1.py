import datetime
import json
import routes
from routes.middleware import RoutesMiddleware
import webob
import webob.dec
import webob.exc


class APIMapper(routes.Mapper):
    def routematch(self, url=None, environ=None):
        if url is None:
            result = self._match("", environ)
            return result[0], result[1]
        return routes.Mapper.routematch(self, url, environ)


class Router(object):
    def __init__(self, mapper):
        mapper.redirect("", "/")
        self.map = mapper
        self._router = RoutesMiddleware(self._dispatch, self.map)

    @classmethod
    def factory(cls, global_conf, **kwargs):
        return cls(APIMapper())

    @webob.dec.wsgify
    def __call__(self, req):
        return self._router

    @staticmethod
    @webob.dec.wsgify
    def _dispatch(req):
        match = req.environ['wsgiorg.routing_args'][1]
        if not match:
            return webob.exc.HTTPNotFound()
        app = match['controller']
        return app


class Request(webob.Request):
    def best_match_content_type(self):

        supported = ('application/json',)
        bm = self.accept.best_match(supported)
        return bm or 'application/json'

    def get_content_type(self, allowed_content_types):

        if 'Content-type' not in self.headers:
            return

        content_type = self.content_type

        if content_type not in allowed_content_types:
            return
        else:
            return content_type


class JSONRequestDeserializer(object):
    def has_body(self, request):

        if 'transfer-encoding' in request.headers:
            return True
        elif request.content_length > 0:
            return True

        return False

    def _sanitizer(self, obj):

        return obj

    def from_json(self, datastring):
        try:
            return json.loads(datastring, object_hook=self._sanitizer)
        except ValueError:
            msg = _('Malformed JSON in request body.')
            raise webob.exc.HTTPBadRequest(explanation=msg)

    def default(self, request):
        if self.has_body(request):
            return {'body': self.from_json(request.body)}
        else:
            return {}


class JSONResponseSerializer(object):
    def _sanitizer(self, obj):

        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        return obj

    def to_json(self, data):
        return json.dumps(data, default=self._sanitizer)

    def default(self, response, result):
        response.content_type = 'application/json'
        response.body = self.to_json(result)


class Resource(object):
    def __init__(self, controller, deserializer=None, serializer=None):
        self.controller = controller
        self.serializer = serializer or JSONResponseSerializer()
        self.deserializer = deserializer or JSONRequestDeserializer()

    @webob.dec.wsgify(RequestClass=Request)
    def __call__(self, request):

        action_args = self.get_action_args(request.environ)
        action = action_args.pop('action', None)

        deserialized_request = self.dispatch(self.deserializer,
                                             action, request)
        action_args.update(deserialized_request)

        action_result = self.dispatch(self.controller, action,
                                      request, **action_args)
        try:
            response = webob.Response(request=request)
            self.dispatch(self.serializer, action, response, action_result)
            return response
        except webob.exc.HTTPException as e:
            return e
        except Exception:
            return action_result

    def dispatch(self, obj, action, *args, **kwargs):

        try:
            method = getattr(obj, action)
        except AttributeError:
            method = getattr(obj, 'default')

        return method(*args, **kwargs)

    def get_action_args(self, request_environment):

        try:
            args = request_environment['wsgiorg.routing_args'][1].copy()
        except Exception:
            return {}

        try:
            del args['controller']
        except KeyError:
            pass

        try:
            del args['format']
        except KeyError:
            pass

        return args

