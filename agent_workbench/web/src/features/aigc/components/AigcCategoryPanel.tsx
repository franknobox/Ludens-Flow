import React from "react";
import type { AigcCategory } from "../types";

interface AigcCategoryPanelProps {
  categories: AigcCategory[];
  activeCategoryId: string;
  onSelectCategory: (id: string) => void;
  isLoading: boolean;
}

export function AigcCategoryPanel({
  categories,
  activeCategoryId,
  onSelectCategory,
  isLoading,
}: AigcCategoryPanelProps) {
  return (
    <aside className="aigc-sidebar">
      <div className="aigc-sidebar-header">
        <span>✨</span>
        <span>AIGC 能力中心</span>
      </div>
      <nav className="aigc-sidebar-nav">
        {isLoading ? (
          <div className="aigc-nav-item" style={{ justifyContent: "center" }}>
            <span className="aigc-loading-spinner" style={{ width: 16, height: 16, marginBottom: 0 }} />
          </div>
        ) : (
          categories.map((cat) => (
            <button
              key={cat.id}
              className={`aigc-nav-item ${activeCategoryId === cat.id ? "is-active" : ""}`}
              onClick={() => onSelectCategory(cat.id)}
            >
              <span className="aigc-nav-icon">{cat.icon}</span>
              <span className="aigc-nav-text">{cat.name}</span>
            </button>
          ))
        )}
      </nav>
    </aside>
  );
}
