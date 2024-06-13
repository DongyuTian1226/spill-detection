from flask import Flask, request, jsonify

def localTest():
    # run an local http
    app = Flask(__name__)
    @app.route('/',  methods=['GET', 'POST'])
    def index():
        print(request.method, request.is_json)
        print('*****')
        print(request.get_json())
        print('*****')
        if request.method == 'GET':
            s = "Hello, this is a GET request."
            print(s)
            return s
        elif request.method == 'POST':
            data = request.get_json()  # 获取POST请求中的json数据
            s = f"Hello, this is a POST request with data: {data}"
            print(s)
            return s
        # 检查post请求是否是JSON格式
        if request.is_json:  # 检查请求是否是JSON格式
            data = request.get_json()
            # 进行处理或响应
            r = jsonify({"message": "Data received successfully", "data": data})
            print(r)
            return r
        else:
            r = jsonify({"error": "Invalid data format, JSON expected"})
            print(r)
            return r
    # def hello():
    #     return 'Hello, World!222'
    app.run(port=5000)


if __name__ == '__main__':
    localTest()
