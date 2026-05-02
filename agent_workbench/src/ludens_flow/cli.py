"""
文件功能：旧版 CLI 模块兼容入口。
核心内容：转发到当前正式入口 ludens_flow.app.cli。
核心内容：避免已安装的旧 console script 仍引用 ludens_flow.cli 时启动失败。
"""

from ludens_flow.app.cli import main


if __name__ == "__main__":
    main()
