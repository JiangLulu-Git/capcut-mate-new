import requests
from tests.api_helpers import unwrap_test_response


def test_create_draft_with_custom_params():
    """测试使用自定义参数创建草稿"""
    # 测试不同的参数值
    test_cases = [
        (1080, 1920),  # 默认值
        (720, 1280),   # 720p
        (2160, 3840)   # 4K
    ]

    # 假设API运行在本地8000端口
    base_url = "http://localhost:60000"
    endpoint = "/openapi/v1/create_draft"
    url = f"{base_url}{endpoint}"

    for height, width in test_cases:
        print(f"Testing with height={height}, width={width}")
        # 使用JSON body传递参数
        try:
            response = requests.post(
                url,
                json={"height": height, "width": width}
            )
            print(f"Response status code: {response.status_code}")
            print(f"Response body: {unwrap_test_response(response)}")
            
            if response.status_code != 200:
                print(f"Error: Request failed with status code {response.status_code}")
                continue

            if "message" not in unwrap_test_response(response) or "draft_id" not in unwrap_test_response(response):
                print("Error: Response missing required fields")
                continue

            if unwrap_test_response(response)["message"] != "草稿创建成功":
                print(f"Error: Unexpected message: {unwrap_test_response(response)['message']}")
                continue

            print("Test passed!")
        except Exception as e:
            print(f"Error occurred: {e}")
            print("Make sure the server is running on http://localhost:8000")


if __name__ == "__main__":
    test_create_draft_with_custom_params()