# API 统一响应规范

所有 `/openapi/capcut-mate/v1/*` JSON 接口均经 `ResponseMiddleware` 包装为：

```json
{
  "code": 1,
  "message": "成功",
  "data": { }
}
```

## 字段说明

| 字段 | 说明 |
|------|------|
| code | **1** = 成功；其它为业务/参数/系统错误码（见 `exceptions.CustomError`） |
| message | 接口级提示（成功多为「成功」，失败为具体原因） |
| data | 业务载荷；失败时为 `null` |

## 客户端解析

```javascript
const json = await res.json();
if (json.code !== 1) throw new Error(json.message);
const payload = json.data; // 业务字段在此
```

```python
from src.schemas.api_standard import unwrap_api_response

payload = unwrap_api_response(response.json())
```

## 请求体

除 `upload_draft`（multipart 上传 zip）外，POST 接口均使用 `Content-Type: application/json`。

## 与旧版差异

| 旧版 | 新版 |
|------|------|
| `code: 0` 成功 | `code: 1` 成功 |
| 业务字段与 `code` 同级 | 业务字段在 `data` 内 |
