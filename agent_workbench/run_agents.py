import logging
import sys
from pathlib import Path

# 添加 src 到路径，方便绝对导入
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import ludens_flow.state as st
from ludens_flow.graph import graph_step

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

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

        print(f"\n[Current Phase]: {phase}")
        if err:
            print(f"[⚠️ WARNING]: Recovered from error: {err}")
            state.last_error = None # 显示过即消
            st.save_state(state)
        
        # 对于特殊的等待节点，给出明确提示
        if phase == "POST_REVIEW_DECISION":
             print("\n> [ACTION REQUIRED] Review completed. Please route next steps:")
             print("  A: Redirect back to DISCUSS phase to fix targets.")
             print("  C: Force Approve and proceed to DEV_COACHING.")
             
        try:
            # 仅做纯净的 IO 与发送
            user_input = input("\n[Ludens Flow]> ").strip()
            if user_input.lower() in ("exit", "quit", "q"):
                logger.info("Saving state and exiting...")
                st.save_state(state)
                break
                
            if not user_input:
                continue

            print("\n>> Graph Engine Working...\n")
            # 不包揽任何分发或修改权限，一律喂给 Graph
            state = graph_step(state, user_input)
            
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
