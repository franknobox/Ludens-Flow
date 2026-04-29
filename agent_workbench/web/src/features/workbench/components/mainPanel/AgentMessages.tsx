import { memo, useMemo } from "react";

import { MarkdownRenderer } from "./MarkdownRenderer";
import { agentName } from "../../utils";
import type {
  AgentKey,
  HistoryByAgent,
  RenderMessage,
  ToolProgressEvent,
  TransientChat,
  WorkflowAction,
} from "../../types";

interface AgentMessagesProps {
  agentKey: AgentKey;
  currentAgent: AgentKey;
  readOnly: boolean;
  requestInFlight: boolean;
  historyByAgent: HistoryByAgent;
  transientChat: TransientChat | null;
  actions: WorkflowAction[];
  onAction: (actionId: string) => void;
}

function renderMessageRow(agentKey: AgentKey, item: RenderMessage, index: number) {
  const user = item.role === "user";
  const sender = user ? "你" : agentName(agentKey);
  const avatar = user ? "ME" : sender.slice(0, 1).toUpperCase();

  return (
    <div className={"msg " + (user ? "user" : "agent")} key={`${agentKey}-${index}-${item.role}`}>
      <div className="avatar">{avatar}</div>
      <div>
        <div className="sender">
          {sender} · {item.phase || ""}
        </div>
        {item.thinking ? (
          <div className="bubble thinking">
            <span>思考中</span>
            <span className="thinking-dots">
              <span></span>
              <span></span>
              <span></span>
            </span>
          </div>
        ) : user ? (
          <div className="bubble bubble-user">{item.content}</div>
        ) : (
          <div className="bubble bubble-agent">
            <MarkdownRenderer content={item.content} />
          </div>
        )}
      </div>
    </div>
  );
}

function toolStatusLabel(type: ToolProgressEvent["type"]): string {
  if (type === "permission_required") return "权限校验";
  if (type === "permission_granted") return "已授权";
  if (type === "permission_denied") return "已拒绝";
  if (type === "tool_started") return "进行中";
  if (type === "tool_progress") return "执行中";
  if (type === "file_changed") return "文件变更";
  if (type === "tool_completed") return "已完成";
  return "失败";
}

function toolEventClass(type: ToolProgressEvent["type"]): string {
  if (type === "permission_denied" || type === "tool_failed") return "failed";
  if (
    type === "permission_granted" ||
    type === "file_changed" ||
    type === "tool_completed"
  ) {
    return "completed";
  }
  return "started";
}

function toolEventDetail(event: ToolProgressEvent): string {
  const parts = [
    event.message,
    event.tool_result_summary,
    event.file_path
      ? `文件：${event.file_path}${event.change_type ? `（${event.change_type}）` : ""}`
      : "",
  ].filter(Boolean);
  return parts.join("\n");
}

function ToolProcessCard({ toolEvents }: { toolEvents: ToolProgressEvent[] }) {
  return (
    <div className="tool-process-card">
      <div className="tool-process-title">执行过程</div>
      <div className="tool-process-list">
        {toolEvents.map((event) => (
          <div
            key={event.id}
            className={`tool-process-item is-${toolEventClass(event.type)}`}
          >
            <div className="tool-process-head">
              <strong>{event.tool_summary}</strong>
              <span>{toolStatusLabel(event.type)}</span>
            </div>
            {toolEventDetail(event) ? (
              <div className="tool-process-detail">{toolEventDetail(event)}</div>
            ) : null}
            {event.error ? <div className="tool-process-detail error">{event.error}</div> : null}
          </div>
        ))}
      </div>
    </div>
  );
}

export const AgentMessages = memo(function AgentMessages(props: AgentMessagesProps) {
  const {
    agentKey,
    currentAgent,
    readOnly,
    requestInFlight,
    historyByAgent,
    transientChat,
    actions,
    onAction,
  } = props;

  const messageRows = useMemo(() => {
    const rows: RenderMessage[] = [...(historyByAgent[agentKey] || [])];
    if (transientChat && transientChat.agentKey === agentKey) {
      rows.push({
        role: "user",
        content: transientChat.userText,
        phase: transientChat.phase,
      });
      if (transientChat.assistantText || transientChat.thinking) {
        rows.push({
          role: "assistant",
          content: transientChat.assistantText || "",
          phase: transientChat.phase,
          thinking: transientChat.thinking && !transientChat.assistantText,
        });
      }
    }
    return rows;
  }, [agentKey, historyByAgent, transientChat]);

  const maxRenderMessages = 160;
  const hiddenCount =
    messageRows.length > maxRenderMessages
      ? messageRows.length - maxRenderMessages
      : 0;
  const visibleRows =
    hiddenCount > 0 ? messageRows.slice(-maxRenderMessages) : messageRows;

  const shouldRenderActions =
    agentKey === currentAgent &&
    !readOnly &&
    !requestInFlight &&
    actions.length > 0;

  return (
    <div className="messages">
      {visibleRows.length ? (
        <>
          {hiddenCount > 0 ? (
            <div className="history-hint">
              较早的消息已折叠：隐藏 {hiddenCount} 条，当前展示最近 {maxRenderMessages} 条。
            </div>
          ) : null}
          {visibleRows.map((item, index) => renderMessageRow(agentKey, item, index))}
          {transientChat && transientChat.agentKey === agentKey && transientChat.toolEvents?.length ? (
            <ToolProcessCard toolEvents={transientChat.toolEvents} />
          ) : null}
        </>
      ) : (
        <div className="empty">
          当前项目里还没有 {agentName(agentKey)} 的对话记录。
        </div>
      )}

      {shouldRenderActions ? (
        <div className="message-actions">
          <p className="title">流程操作</p>
          <div className="row">
            {actions.map((action) => (
              <button
                key={action.id}
                type="button"
                disabled={requestInFlight}
                onClick={() => onAction(action.id)}
              >
                {action.label || action.id}
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
});
