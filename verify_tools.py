from pathlib import Path
import sys

# 添加 src 到路径，方便绝对导入
sys.path.insert(0, str(Path(__file__).resolve().parent / "agent_workbench" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "agent_workbench"))

from ludens_flow.tools.search import web_search
from agent_workbench.run_agents import parse_user_input

def test_web_search():
    print("\n--- Testing Web Search ---")
    query = "latest unity engine version"
    print(f"Querying: {query}")
    try:
        result = web_search(query, max_results=2)
        print("Results:")
        print(result[:500] + "...\n(Truncated for test output)")
    except Exception as e:
        print(f"Search failed: {e}")

def test_image_parsing():
    print("\n--- Testing Image Parsing ---")
    # 创建一个哑样本测试解析文件逻辑
    test_img = Path("test_dummy.png")
    test_img.touch()
    
    input_str = "Look at this error test_dummy.png please"
    print(f"Original Input: {input_str}")
    
    parsed = parse_user_input(input_str)
    print("Parsed result type:", type(parsed))
    if isinstance(parsed, list):
        for item in parsed:
             if item["type"] == "text":
                 print(f"Text Content: {item['text']}")
             elif item["type"] == "image_url":
                  url = item['image_url']['url']
                  print(f"Image Content: {url[:30]}... (Base64 Truncated)")
    
    test_img.unlink()

if __name__ == "__main__":
    test_web_search()
    test_image_parsing()
    print("\n✅ Verification tests complete.")
