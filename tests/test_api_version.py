import pytest
from tests.api_helpers import unwrap_test_response
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_v1_create_draft():
    """测试v1版本的create_draft接口"""
    response = client.post("/openapi/v1/create_draft", params={"height": 1080, "width": 1920})
    assert response.status_code == 200
    assert "message" in unwrap_test_response(response)
    assert "draft_id" in unwrap_test_response(response)
    assert unwrap_test_response(response)["message"] == "草稿创建成功"


def test_version_not_found():
    """测试不存在的API版本"""
    response = client.post("/openapi/v2/create_draft", params={"height": 1080, "width": 1920})
    assert response.status_code == 404


if __name__ == "__main__":
    # 运行测试
    pytest.main(["-v", "test_api_version.py"])