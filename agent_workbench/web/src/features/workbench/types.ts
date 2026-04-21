// 文件功能：Workbench 前端类型导出入口，按业务域组织并统一对外暴露。
// 核心内容：内部拆分为 core/project/workspace/chat/view 五类类型文件。
// 核心内容：保持对现有页面导入路径兼容，支持后续功能扩展时按域演进。

export * from "./types/core";
export * from "./types/project";
export * from "./types/workspace";
export * from "./types/chat";
export * from "./types/view";
