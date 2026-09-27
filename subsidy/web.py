"""极简 WSGI 框架：路由、请求解析（含 multipart 文件上传）、签名会话。"""
import base64
import hashlib
import hmac
import http.cookies
import json
import os
import re
import urllib.parse

# 会话签名密钥：生产环境通过环境变量注入；未设置时随机生成（重启后会话失效）
SECRET = os.environ.get("SUBSIDY_SECRET") or os.urandom(32).hex()

ROUTES = []


def route(method, pattern):
    """注册路由，路径支持 <int:name> 参数。"""
    regex = re.sub(r"<int:(\w+)>", r"(?P<\1>\\d+)", pattern)
    compiled = re.compile("^" + regex + "$")

    def decorator(func):
        ROUTES.append((method, compiled, func))
        return func

    return decorator


class Response:
    def __init__(self, body="", status="200 OK",
                 content_type="text/html; charset=utf-8", headers=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.body = body
        self.status = status
        self.headers = list(headers or [])
        self.headers.append(("Content-Type", content_type))


def redirect(location):
    return Response("", "303 See Other", headers=[("Location", location)])


def not_found(msg="页面不存在或无权访问"):
    return Response(
        "<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'><title>404</title></head>"
        "<body style='font-family:sans-serif;padding:40px'>"
        "<h2>404</h2><p>" + msg + "</p><p><a href='/'>返回首页</a></p></body></html>",
        "404 Not Found")


class Request:
    def __init__(self, environ):
        self.method = environ["REQUEST_METHOD"]
        self.path = environ.get("PATH_INFO", "/")
        self.query = {k: v[0] for k, v in
                      urllib.parse.parse_qs(environ.get("QUERY_STRING", "")).items()}
        self.cookies = http.cookies.SimpleCookie(environ.get("HTTP_COOKIE", ""))
        self.form = {}
        self.files = {}
        if self.method in ("POST", "PUT", "PATCH"):
            self._parse_body(environ)

    def _parse_body(self, environ):
        try:
            length = int(environ.get("CONTENT_LENGTH") or 0)
        except ValueError:
            length = 0
        body = environ["wsgi.input"].read(length) if length > 0 else b""
        ctype = environ.get("CONTENT_TYPE", "")
        if ctype.startswith("application/x-www-form-urlencoded"):
            self.form = {k: v[0] for k, v in
                         urllib.parse.parse_qs(body.decode("utf-8", "replace")).items()}
        elif ctype.startswith("multipart/form-data"):
            m = re.search(r"boundary=([^;]+)", ctype)
            if m:
                self._parse_multipart(body, m.group(1).strip().strip('"'))

    def _parse_multipart(self, body, boundary):
        delimiter = b"--" + boundary.encode()
        for seg in body.split(delimiter):
            seg = seg.strip(b"\r\n")
            if not seg or seg == b"--":
                continue
            if seg.endswith(b"--"):
                seg = seg[:-2].rstrip(b"\r\n")
            head, sep, content = seg.partition(b"\r\n\r\n")
            if not sep:
                continue
            head_text = head.decode("utf-8", "replace")
            m_name = re.search(r'name="([^"]+)"', head_text)
            if not m_name:
                continue
            name = m_name.group(1)
            m_file = re.search(r'filename="([^"]*)"', head_text)
            if m_file and m_file.group(1):
                self.files[name] = (m_file.group(1), content)
            else:
                self.form[name] = content.decode("utf-8", "replace")


# ---------------------------------------------------------------- 会话

def make_session_cookie(user_id):
    payload = base64.urlsafe_b64encode(json.dumps({"uid": user_id}).encode()).decode()
    sig = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return payload + "." + sig


def parse_session(value):
    try:
        payload, sig = value.rsplit(".", 1)
        expected = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        return json.loads(base64.urlsafe_b64decode(payload.encode()))["uid"]
    except Exception:
        return None


# ---------------------------------------------------------------- 应用入口

def application(environ, start_response):
    req = Request(environ)
    resp = None
    for method, regex, func in ROUTES:
        if method != req.method:
            continue
        m = regex.match(req.path)
        if m:
            kwargs = {k: int(v) for k, v in m.groupdict().items()}
            resp = func(req, **kwargs)
            break
    if resp is None:
        resp = not_found()
    headers = resp.headers + [("Content-Length", str(len(resp.body)))]
    start_response(resp.status, headers)
    return [resp.body]
