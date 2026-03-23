import logging
import sys
import base64
import mimetypes
import re
import io
from pathlib import Path

# 添加 src 到路径，方便绝对导入
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

try:
    from dotenv import load_dotenv
    # run_agents.py is in agent_workbench/, so parent is the root dir where .env lives
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

import ludens_flow.state as st
from ludens_flow.graph import graph_step

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

from typing import Union


def _extract_image_path_candidates(text: str) -> list[tuple[str, str]]:
    """Return [(matched_text, path_text)] for likely local image paths."""
    ext_pattern = r"(?:png|jpg|jpeg|webp)"
    patterns = [
        rf'(?P<matched>"(?P<path>[^"\r\n]+\.(?:{ext_pattern}))")',
        rf"(?P<matched>'(?P<path>[^'\r\n]+\.(?:{ext_pattern}))')",
        rf"(?P<matched>(?<!\S)(?P<path>(?:[A-Za-z]:[\\/]|\.{{1,2}}[\\/]|[\\/])[^\r\n<>|?*]+?\.(?:{ext_pattern}))(?=$|\s))",
        rf'(?P<matched>(?<!\S)(?P<path>[A-Za-z0-9_.\-\\/]+\.(?:{ext_pattern}))(?=$|\s))',
    ]

    seen: set[tuple[str, str]] = set()
    candidates: list[tuple[str, str]] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            matched_text = match.group("matched")
            path_text = match.group("path")
            key = (matched_text, path_text)
            if key in seen:
                continue
            if any(path_text in existing_path for _, existing_path in candidates):
                continue
            seen.add(key)
            candidates.append((matched_text, path_text))
    return candidates

def parse_user_input(text: str) -> Union[str, list]:
    """
    Parse the user input for local file paths representing images.
    If an image is found, convert the file to a base64 data URI and 
    return a multimodal payload list. Otherwise returning the string.
    """
    payload = []
    text_content = text

    for matched_text, file_path_str in _extract_image_path_candidates(text):
        path = Path(file_path_str)
        if path.is_file():
            try:
                # 尝试使用 PIL 自动压缩过大的图片，防止 Token 超出大模型限制 (e.g 128k)
                try:
                    from PIL import Image
                    with Image.open(path) as img:
                        # Convert to RGB to avoid issues with saving alpha channels as JPEG
                        if img.mode in ("RGBA", "P"):
                            img = img.convert("RGB")
                            
                        # Resize if too large (e.g., max width/height 512 to strictly ensure < 128k base64 characters)
                        max_size = (512, 512)
                        img.thumbnail(max_size, Image.Resampling.LANCZOS)
                        
                        # Compress and save to bytes
                        buffered = io.BytesIO()
                        img.save(buffered, format="JPEG", quality=75)
                        base64_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
                        mime_type = "image/jpeg"
                        
                except ImportError:
                    # 如果没有装 Pillow，回退到原始读取 (可能会超 token)
                    logger.warning("Pillow (PIL) not installed. Large images might exceed LLM token limits. 'pip install Pillow' is recommended.")
                    with open(path, "rb") as image_file:
                        base64_str = base64.b64encode(image_file.read()).decode('utf-8')
                    mime_type, _ = mimetypes.guess_type(path)
                    if not mime_type:
                        mime_type = "image/png"
                    
                data_uri = f"data:{mime_type};base64,{base64_str}"
                
                payload.append({
                    "type": "image_url",
                    "image_url": {
                        "url": data_uri
                    }
                })
                # Remove the path from the text so it doesn't clutter the LLM context unnecessarily
                text_content = text_content.replace(matched_text, "").strip()
            except Exception as e:
                logger.warning(f"Could not read image file {path}: {e}")
                
    if not payload:
        return text.strip()
        
    # Prepend the text to the payload
    if text_content:
        payload.insert(0, {
            "type": "text",
            "text": text_content
        })
        
    return payload

def main():
    logger.info("Initializing workspace...")
    st.init_workspace()
    
    logger.info("Loading state...")
    state = st.load_state()

    print("\n" + "="*50)
    print(" Ludens Flow V2 Graph Runner ")
    print("="*50 + "\n")
    
    while True:
        # 显示当前身位和重要错误
        phase = state.phase
        err = getattr(state, "last_error", None)

        if phase == "DEV_COACHING":
            print("\n" + "★"*50)
            print(" 🎓 [DEV COACHING MODE ACTIVE] - ASK ME ANYTHING! ")
            print("★"*50)
            print("> You are now conversing with the Engineering Agent Coach.")
            print("> (Main artifacts are currently FROZEN. Type your questions below)")
        else:
            print(f"\n[Current Phase]: {phase}")
        if err:
            print(f"[⚠️ WARNING]: Recovered from error: {err}")
            state.last_error = None # 显示过即消
            st.save_state(state)
        
        # 对于特殊的等待节点，给出明确提示
        if phase == "POST_REVIEW_DECISION":
             print("\n> [ACTION REQUIRED] Review completed. Please route next steps:")
             print("  A: Redirect back to DISCUSS phase to fix targets.")
             print("  B: Only fix BLOCK/MAJOR issues (skip minor ones).")
             print("  C: Force Approve and proceed to DEV_COACHING.")
             
        try:
            # 仅做纯净的 IO 与发送
            raw_input = input("\n[Ludens Flow]> ").strip()
            
            if raw_input.lower() in ("exit", "quit", "q"):
                logger.info("Saving state and exiting...")
                st.save_state(state)
                break
                
            if not raw_input:
                continue
                
            if raw_input.lower() in ("/reset", "/restart"):
                logger.info("Resetting workspace state...")
                # 重新加载（会自动拿到全新的纯净状态）
                state = st.reset_workspace_state(clear_images=True)
                print("\n✨ [System]: 记忆已清空，时空倒流回起点！")
                continue

            # Parse input for potential images
            user_input = parse_user_input(raw_input)
            
            print("\n>> Graph Engine Working...\n")
            # 不包揽任何分发或修改权限，一律喂给 Graph
            state = graph_step(state, user_input)
            
            # 若有模型自然语言返回，则立刻打印回显
            if getattr(state, "last_assistant_message", None):
                print(f"\n[🤖 Agent Reply]:\n{state.last_assistant_message}\n")
                state.last_assistant_message = None  # 显示完即消
                st.save_state(state)
            
        except KeyboardInterrupt:
            print("\nInterrupted by user. Exiting...")
            st.save_state(state)
            break
        except Exception as e:
            # Runner 级别的防崩保护，即便 Graph 也炸了最后拖底
            logger.error(f"Fatal Runner error: {e}")
            st.save_state(state)
            print("System halted safely. Run again to resume.")
            break

if __name__ == "__main__":
    main()
