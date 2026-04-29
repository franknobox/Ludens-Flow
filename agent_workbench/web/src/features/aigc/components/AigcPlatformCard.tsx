import React from "react";
import type { AigcPlatform } from "../types";

interface AigcPlatformCardProps {
  platform: AigcPlatform;
}

export function AigcPlatformCard({ platform }: AigcPlatformCardProps) {
  const statusLabel = {
    online: "可访问",
    maintenance: "🟡 维护中",
    coming_soon: "⏳ 敬请期待",
  }[platform.status];

  return (
    <a className="aigc-card" href={platform.url} target="_blank" rel="noreferrer">
      <div className="aigc-card-header">
        <div>
          <div className="aigc-card-title">{platform.name}</div>
          <div className="aigc-card-url">{platform.url.replace(/^https?:\/\//, "")}</div>
        </div>
        <div className={`aigc-card-status ${platform.status}`}>
          {platform.region === "china" ? "国内" : statusLabel}
        </div>
      </div>
      <div className="aigc-card-desc">{platform.description}</div>
      <div className="aigc-card-tags">
        {platform.supported_types.map((type) => (
          <span key={type} className="aigc-card-tag">
            {type}
          </span>
        ))}
      </div>
      <div className="aigc-card-open">打开网站 ↗</div>
    </a>
  );
}
