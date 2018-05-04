# -*- coding:utf-8 -*-
# Tested with Python 2.7.9, Linux & Mac OS X
import socket
import StringIO
import sys


class WSGIServer(object):

    address_family = socket.AF_INET  # IPV4 地址族 (如 AF_INET 用于服务器之间的通信, AF_UNIX 用于单一 UNIX 系统进程间的通信)
    socket_type = socket.SOCK_STREAM  # 数据流式的套接字 (数据接收的方式, 数据流方式用于 TCP, 而如 SOCK_DGRAM 为数据报方式——用于 UDP)
    request_queue_size = 1  # 请求接收队列大小

    def __init__(self, server_address):
        # Create a listening socket 创建一个监听套接字
        self.listen_socket = listen_socket = socket.socket(
            self.address_family,
            self.socket_type
        )

        # Allow to reuse the same address 设置该 socket 的地址可重用
        # 可重用: 当 socket 关闭后, 本地端用于该 socket 的端口号立刻可以被重用
        #   具体来说: 操作系统会在服务器 socket 被关闭或服务器进程终止后马上释放该服务器的端口, 否则操作系统会保留几分钟该端口
        listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        #   指定 level=SOL_SOCKET 表示要设置的是 SOCKET 选项 (其他的还有 SOL_TCP 等, 表示要设置的是 TCP 选项)
        #   optname=SO_REUSEADDR 表示要设置的是 SOCKET 的 REUSEADDR 选项 (其他可设置的 SOCKET 选项为 SO_XXX)
        #   value=1 表示设置 SOCKET 的 REUSEADDR 选项值为 1
        #   (如果是SOL_TCP, 则可设置的选项为 TCP_XXX)

        # Bind 绑定服务器地址
        listen_socket.bind(server_address)

        # Activate 启动监听
        listen_socket.listen(self.request_queue_size)

        # Get server host name and port 获取服务器主机名和端口号
        host, port = self.listen_socket.getsockname()[:2]
        self.server_name = socket.getfqdn(host)  # 获取完整的服务器名称
        self.server_port = port

        # Return headers set by Web framework/Web application
        self.headers_set = []

    def set_app(self, application):
        self.application = application

    def serve_forever(self):
        listen_socket = self.listen_socket
        while True:
            # New client connection
            self.client_connection, client_address = listen_socket.accept()  # 在这里阻塞等待,
            # 直到收到一个请求
            # Handle one request and close the client connection. Then
            # loop over to wait for another client connection
            self.handle_one_request()  # 处理该请求, 同时关闭客户端连接,
            # 然后再次循环等待下一个 客户端连接

    def handle_one_request(self):
        self.request_data = request_data = self.client_connection.recv(1024)
        # Print formatted request data a la 'curl -v'
        print(''.join(
            '< {line}\n'.format(line=line)
            for line in request_data.splitlines()
        ))

        self.parse_request(request_data)

        # Construct environment dictionary using request data
        env = self.get_environ()

        # It's time to call our application callable and get
        # back a result that will become HTTP response body
        result = self.application(env, self.start_response)  # 运行你的 pyramid、django、flask 应用

        # 注: finishe_response 用到 self.headers_set
        #     应用需调用 self.start_response 并传入 status 和 response_headers

        # Construct a response and send it back to the client
        self.finish_response(result)  # 运行结束后获得一个结果, 将此结果送回客户端

    def parse_request(self, text):
        request_line = text.splitlines()[0]
        request_line = request_line.rstrip('\r\n')
        # Break down the request line into components
        (self.request_method,  # GET
         self.path,            # /hello
         self.request_version  # HTTP/1.1
         ) = request_line.split()

    def get_environ(self):
        env = {}
        # The following code snippet does not follow PEP8 conventions
        # but it's formatted the way it is for demonstration purposes
        # to emphasize the required variables and their values
        #
        # Required WSGI variables
        env['wsgi.version']      = (1, 0)
        env['wsgi.url_scheme']   = 'http'
        env['wsgi.input']        = StringIO.StringIO(self.request_data)
        env['wsgi.errors']       = sys.stderr
        env['wsgi.multithread']  = False
        env['wsgi.multiprocess'] = False
        env['wsgi.run_once']     = False
        # Required CGI variables
        env['REQUEST_METHOD']    = self.request_method    # GET
        env['PATH_INFO']         = self.path              # /hello
        env['SERVER_NAME']       = self.server_name       # localhost
        env['SERVER_PORT']       = str(self.server_port)  # 8888
        return env

    def start_response(self, status, response_headers, exc_info=None):
        # Add necessary server headers
        server_headers = [
            ('Date', 'Tue, 31 Mar 2015 12:54:48 GMT'),
            ('Server', 'WSGIServer 0.2'),
        ]
        self.headers_set = [status, response_headers + server_headers]
        # To adhere to WSGI specification the start_response must return
        # a 'write' callable. We simplicity's sake we'll ignore that detail
        # for now.
        # return self.finish_response

    def finish_response(self, result):
        try:
            status, response_headers = self.headers_set
            response = 'HTTP/1.1 {status}\r\n'.format(status=status)
            for header in response_headers:
                response += '{0}: {1}\r\n'.format(*header)
            response += '\r\n'
            for data in result:
                response += data
            # Print formatted response data a la 'curl -v'
            print(''.join(
                '> {line}\n'.format(line=line)
                for line in response.splitlines()
            ))
            self.client_connection.sendall(response)
        finally:
            self.client_connection.close()


SERVER_ADDRESS = (HOST, PORT) = '', 8888


def make_server(server_address, application):
    server = WSGIServer(server_address)
    server.set_app(application)
    return server


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit('Provide a WSGI application object as module:callable')
    app_path = sys.argv[1]
    module, application = app_path.split(':')
    module = __import__(module)
    application = getattr(module, application)
    httpd = make_server(SERVER_ADDRESS, application)
    print('WSGIServer: Serving HTTP on port {port} ...\n'.format(port=PORT))
    httpd.serve_forever()
