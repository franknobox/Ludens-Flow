// 文件功能：Workbench 前端 API 访问层，统一封装所有 HTTP 请求。
// 核心内容：提供状态、项目、会话、工作区文件与设置接口调用方法。
// 核心内容：内部按域拆分为 chat/projects/workspace/tools/events 子模块。

import {
  archiveProject,
  createProject,
  deleteProject,
  getCurrentProjectSettings,
  getProjects,
  renameProject,
  resetCurrentProject,
  restoreProject,
  selectProject,
  updateCurrentProjectSettings,
} from "./api/projects";
import { getState, postAction, postChat } from "./api/chat";
import {
  addCurrentWorkspace,
  deleteCurrentWorkspace,
  getCurrentWorkspaces,
  getWorkspaceFileContent,
  getWorkspaceFiles,
  updateWorkspaceFileContent,
} from "./api/workspace";
import { getTools } from "./api/tools";
import { openProjectEvents } from "./api/events";

export const workbenchApi = {
  getState,
  postChat,
  postAction,
  getProjects,
  createProject,
  selectProject,
  renameProject,
  archiveProject,
  restoreProject,
  deleteProject,
  resetCurrentProject,
  getCurrentProjectSettings,
  updateCurrentProjectSettings,
  getWorkspaceFiles,
  getWorkspaceFileContent,
  updateWorkspaceFileContent,
  getCurrentWorkspaces,
  addCurrentWorkspace,
  deleteCurrentWorkspace,
  getTools,
  openProjectEvents,
};
