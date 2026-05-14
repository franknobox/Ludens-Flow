import type { UserProfileResponse } from "../../workbench/types";

interface UserProfileSectionProps {
  profile: UserProfileResponse | null;
  draft: string;
  dirty: boolean;
  loading: boolean;
  submitting: boolean;
  onDraftChange: (value: string) => void;
  onReload: () => void;
  onSave: () => void;
}

export function UserProfileSection(props: UserProfileSectionProps) {
  const {
    profile,
    draft,
    dirty,
    loading,
    submitting,
    onDraftChange,
    onReload,
    onSave,
  } = props;

  return (
    <div className="settings-detail-stack settings-detail-stack--fill">
      <section className="settings-pane-card settings-pane-card-main settings-profile-card">
        <div className="settings-card-head">
          <div>
            <h2 className="settings-card-title">用户画像</h2>
            <p className="settings-card-subtitle">
              编辑当前项目的 USER_PROFILE.md。Agent 会在涉及身份、偏好、目标和约束时优先参考这里。
            </p>
          </div>
          <div className="settings-profile-actions">
            <button
              type="button"
              className="settings-pill-button"
              title="把当前项目磁盘上的 USER_PROFILE.md 再读一遍，覆盖前端编辑框里的内容。"
              disabled={loading || submitting}
              onClick={onReload}
            >
              刷新
            </button>
            <button
              type="button"
              className="settings-primary-button"
              disabled={loading || submitting || !dirty}
              onClick={onSave}
            >
              {submitting ? "保存中..." : "保存画像"}
            </button>
          </div>
        </div>

        <div className="settings-profile-path">
          {profile?.display_path || profile?.path || "当前项目尚未加载 USER_PROFILE.md"}
        </div>

        <label className="settings-field settings-profile-editor">
          <span>USER_PROFILE.md</span>
          <textarea
            value={draft}
            disabled={loading || submitting}
            onChange={(event) => onDraftChange(event.target.value)}
            placeholder="正在加载用户画像..."
          />
        </label>
      </section>
    </div>
  );
}
