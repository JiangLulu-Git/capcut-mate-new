---
name: "api-standardizer"
description: "规范API接口格式，确保POST请求使用JSON参数（文件除外），统一返回结构{code,message,data}。Invoke when creating or modifying API interfaces."
---

# API Standardizer

此skill用于规范API接口的创建和修改，确保所有接口遵循统一的格式标准。

## 适用场景

当需要创建或修改以下内容时，必须调用此skill：
- 新增API接口
- 修改现有API接口
- 重构接口参数或返回结构

## 接口规范标准

### 1. POST请求参数规范

**原则**：除文件上传类型的请求外，所有POST请求必须使用JSON格式传递参数。

#### 正确示例（JSON格式）：
```python
@app.route('/api/user/create', methods=['POST'])
def create_user():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
```

#### 正确示例（文件上传）：
```python
@app.route('/api/upload', methods=['POST'])
def upload_file():
    file = request.files.get('file')
    # 文件上传可以使用multipart/form-data
```

#### 错误示例（非文件类型使用form-data）：
```python
# 错误：非文件类型不应使用form-data
@app.route('/api/user/create', methods=['POST'])
def create_user():
    username = request.form.get('username')  # 应改为JSON格式
```

### 2. 统一返回结构规范

所有接口必须使用以下统一返回格式：

```json
{
    "code": 1,
    "message": "操作成功",
    "data": {}
}
```

#### 字段说明：
- **code**: 状态码，`1`表示成功，其他值表示失败
- **message**: 提示信息，描述操作结果
- **data**: 返回数据，成功时包含具体数据，失败时可为null或错误详情

#### 成功返回示例：
```python
return jsonify({
    "code": 1,
    "message": "创建成功",
    "data": {
        "user_id": 123,
        "username": "test_user"
    }
})
```

#### 失败返回示例：
```python
return jsonify({
    "code": 0,
    "message": "参数错误",
    "data": None
})
```

#### 其他失败状态码示例：
```python
# 参数错误
{"code": 0, "message": "参数错误", "data": null}

# 未授权
{"code": 401, "message": "未授权访问", "data": null}

# 服务器错误
{"code": 500, "message": "服务器内部错误", "data": null}

# 业务逻辑错误
{"code": 1001, "message": "用户已存在", "data": null}
```

### 3. 完整接口示例

```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/api/user/create', methods=['POST'])
def create_user():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "code": 0,
                "message": "参数不能为空",
                "data": None
            }), 400
        
        username = data.get('username')
        email = data.get('email')
        
        if not username or not email:
            return jsonify({
                "code": 0,
                "message": "用户名和邮箱不能为空",
                "data": None
            }), 400
        
        # 业务逻辑处理
        user_id = create_user_in_db(username, email)
        
        return jsonify({
            "code": 1,
            "message": "创建成功",
            "data": {
                "user_id": user_id,
                "username": username,
                "email": email
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"服务器错误: {str(e)}",
            "data": None
        }), 500
```

### 4. 文件上传接口示例

```python
@app.route('/api/file/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({
                "code": 0,
                "message": "未上传文件",
                "data": None
            }), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({
                "code": 0,
                "message": "文件名为空",
                "data": None
            }), 400
        
        # 保存文件
        file_path = save_file(file)
        
        return jsonify({
            "code": 1,
            "message": "上传成功",
            "data": {
                "file_path": file_path,
                "file_name": file.filename
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"上传失败: {str(e)}",
            "data": None
        }), 500
```

## 检查清单

创建或修改接口时，请确认：
- [ ] POST请求使用JSON格式传递参数（文件上传除外）
- [ ] 返回结构包含code、message、data三个字段
- [ ] code为1表示成功，其他值表示失败
- [ ] message字段提供清晰的提示信息
- [ ] data字段在成功时包含数据，失败时为null或错误详情
- [ ] 异常处理也遵循统一返回格式
