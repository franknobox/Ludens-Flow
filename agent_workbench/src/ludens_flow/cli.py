import argparse
import logging
import os
import sys

import ludens_flow.state as st
from ludens_flow.bootstrap import load_env_if_available
from ludens_flow.graph import graph_step
from ludens_flow.input_parser import parse_user_input
from ludens_flow.paths import (
    clear_project_unity_root,
    create_project,
    get_project_unity_root,
    list_projects,
    resolve_project_id,
    set_active_project_id,
    set_project_unity_root,
)
from ludens_flow.router import action_user_input, get_available_actions

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _read_nav_key() -> str:
    if os.name == "nt":
        import msvcrt

        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            code = msvcrt.getwch()
            if code == "H":
                return "up"
            if code == "P":
                return "down"
            return "other"
        if ch in ("\r", "\n"):
            return "enter"
        if ch == "\x1b":
            return "esc"
        return "other"

    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            seq = sys.stdin.read(2)
            if seq == "[A":
                return "up"
            if seq == "[B":
                return "down"
            return "esc"
        if ch in ("\r", "\n"):
            return "enter"
        return "other"
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _pick_workflow_action(actions: list[dict]) -> str | None:
    if not actions:
        return None

    index = 0
    print("\n[Workflow Options] 使用 ↑/↓ 选择，Enter 确认，Esc 取消")
    for idx, action in enumerate(actions, start=1):
        print(f"  {idx}. {action.get('label', action.get('id', ''))}")
    print(
        f"Current: {actions[index].get('label', actions[index].get('id', ''))}",
        end="",
        flush=True,
    )

    while True:
        nav = _read_nav_key()
        if nav == "up":
            index = (index - 1) % len(actions)
            print(
                f"\rCurrent: {actions[index].get('label', actions[index].get('id', ''))}    ",
                end="",
                flush=True,
            )
        elif nav == "down":
            index = (index + 1) % len(actions)
            print(
                f"\rCurrent: {actions[index].get('label', actions[index].get('id', ''))}    ",
                end="",
                flush=True,
            )
        elif nav == "enter":
            print()
            return str(actions[index].get("id", "")).strip() or None
        elif nav == "esc":
            print()
            return None


def _safe_save_state(state) -> None:
    """尽力保存状态；如果文件被其他进程占用，则只告警，不让 CLI 退出流程再崩一次。"""
    try:
        st.save_state(state)
    except PermissionError as e:
        logger.warning(f"State file is locked by another process, skipping save: {e}")
    except Exception as e:
        logger.warning(f"Failed to save state: {e}")


def run_cli_loop() -> None:
    logger.info("Initializing workspace...")
    st.init_workspace()

    logger.info("Loading state...")
    state = st.load_state()

    print("\n" + "=" * 50)
    print(" Ludens Flow V2 Graph Runner ")
    print("=" * 50 + "\n")

    while True:
        phase = state.phase
        err = getattr(state, "last_error", None)
        project_label = state.project_id or "(unknown)"

        print(f"\n[Current Project]: {project_label}")

        if phase == "DEV_COACHING":
            print("\n" + "★" * 50)
            print(" 🎓 [DEV COACHING MODE ACTIVE] - ASK ME ANYTHING! ")
            print("★" * 50)
            print("> You are now conversing with the Engineering Agent Coach.")
            print("> (Main artifacts are currently FROZEN. Type your questions below)")
        else:
            print(f"\n[Current Phase]: {phase}")
        if err:
            print(f"[⚠️ WARNING]: Recovered from error: {err}")
            state.last_error = None
            _safe_save_state(state)

        if phase == "POST_REVIEW_DECISION":
            print("\n> [ACTION REQUIRED] Review completed. Please route next steps:")
            print("  Use '/choose' to select a workflow option.")

        workflow_actions = get_available_actions(state)
        if workflow_actions:
            print("\n[Workflow Options Available]")
            for action in workflow_actions:
                print(f"  - {action.get('label', action.get('id', ''))}")
            print("  输入 /choose 打开上下选择菜单；普通输入仍按对话处理。")

        try:
            raw_input = input("\n[Ludens Flow]> ").strip()

            if raw_input.lower() in ("exit", "quit", "q"):
                logger.info("Saving state and exiting...")
                _safe_save_state(state)
                break

            if not raw_input:
                continue

            if raw_input.lower() in ("/reset", "/restart"):
                logger.info("Resetting current project state...")
                state = st.reset_current_project_state(
                    clear_images=True, project_id=state.project_id
                )
                print("\n✨ [System]: 记忆已清空，时空倒流回起点！")
                continue

            if raw_input.lower() == "/choose":
                selected = _pick_workflow_action(workflow_actions)
                if not selected:
                    continue
                print("\n>> Graph Engine Working...\n")
                state = graph_step(
                    state,
                    action_user_input(selected),
                    explicit_action=selected,
                )

                if getattr(state, "last_assistant_message", None):
                    print(f"\n[🤖 Agent Reply]:\n{state.last_assistant_message}\n")
                    state.last_assistant_message = None
                    _safe_save_state(state)
                continue

            if raw_input.lower() == "/projects":
                projects = list_projects()
                current_project = resolve_project_id(state.project_id)
                print("\n[Projects]")
                print(f"* active: {current_project}")
                if not projects:
                    print("- (no named projects yet)")
                else:
                    for project in projects:
                        marker = "*" if project["id"] == current_project else "-"
                        print(f"{marker} {project['id']}  {project['display_name']}")
                continue

            if raw_input.lower().startswith("/project new "):
                project_id = raw_input[len("/project new ") :].strip()
                if not project_id:
                    print("Usage: /project new <project_id>")
                    continue
                meta = create_project(project_id, set_active=True)
                st.init_workspace(project_id=meta["id"])
                state = st.load_state(project_id=meta["id"])
                print(f"\n✨ [System]: 已创建并切换到项目 {meta['id']}")
                continue

            if raw_input.lower().startswith("/project use "):
                project_id = raw_input[len("/project use ") :].strip()
                if not project_id:
                    print("Usage: /project use <project_id>")
                    continue
                active_project = set_active_project_id(project_id)
                st.init_workspace(project_id=active_project)
                state = st.load_state(project_id=active_project)
                print(f"\n✨ [System]: 已切换到项目 {active_project}")
                continue

            if raw_input.lower().startswith("/unity bind "):
                unity_root = raw_input[len("/unity bind ") :].strip().strip('"')
                if not unity_root:
                    print("Usage: /unity bind <unity_project_path>")
                    continue
                try:
                    meta = set_project_unity_root(
                        unity_root, project_id=state.project_id
                    )
                    print(
                        f"\n✨ [System]: Unity 工程已绑定 -> {meta.get('unity_root', '')}"
                    )
                except Exception as e:
                    print(f"\n[⚠️ WARNING]: Unity 绑定失败: {e}")
                continue

            if raw_input.lower() == "/unity unbind":
                meta = clear_project_unity_root(project_id=state.project_id)
                print(f"\n✨ [System]: 已解除 Unity 绑定 ({meta['id']})")
                continue

            if raw_input.lower() == "/unity status":
                unity_root = get_project_unity_root(project_id=state.project_id)
                if unity_root:
                    print(f"\n[Unity Binding]: {unity_root}")
                else:
                    print("\n[Unity Binding]: (not bound)")
                continue

            user_input = parse_user_input(raw_input)

            print("\n>> Graph Engine Working...\n")
            state = graph_step(state, user_input)

            if getattr(state, "last_assistant_message", None):
                print(f"\n[🤖 Agent Reply]:\n{state.last_assistant_message}\n")
                state.last_assistant_message = None
                _safe_save_state(state)

        except EOFError:
            logger.info("No interactive stdin detected. Exiting CLI runner.")
            _safe_save_state(state)
            break
        except KeyboardInterrupt:
            print("\nInterrupted by user. Exiting...")
            _safe_save_state(state)
            break
        except Exception as e:
            logger.error(f"Fatal Runner error: {e}")
            _safe_save_state(state)
            print("System halted safely. Run again to resume.")
            break


def main() -> None:
    parser = argparse.ArgumentParser(description="Ludens-Flow CLI workbench runner")
    parser.parse_args()
    load_env_if_available()
    run_cli_loop()


if __name__ == "__main__":
    main()
