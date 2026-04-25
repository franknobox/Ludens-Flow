import React, { useEffect, useState } from "react";
import { fetchAigcCategories } from "../api/aigc";
import type { AigcCategory } from "../types";
import { AigcCategoryPanel } from "./AigcCategoryPanel";
import { AigcPlatformCard } from "./AigcPlatformCard";
import "../styles/aigc.css";

export function AigcPage() {
  const [categories, setCategories] = useState<AigcCategory[]>([]);
  const [activeCategoryId, setActiveCategoryId] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    fetchAigcCategories().then((data) => {
      if (mounted) {
        setCategories(data);
        if (data.length > 0) {
          setActiveCategoryId(data[0].id);
        }
        setIsLoading(false);
      }
    });
    return () => {
      mounted = false;
    };
  }, []);

  const activeCategory = categories.find((c) => c.id === activeCategoryId);

  return (
    <div className="aigc-page">
      <AigcCategoryPanel
        categories={categories}
        activeCategoryId={activeCategoryId}
        onSelectCategory={setActiveCategoryId}
        isLoading={isLoading}
      />

      <div className="aigc-main">
        {activeCategory && !isLoading && (
          <>
            <div className="aigc-main-header">
              <div className="aigc-main-title">{activeCategory.name}快捷入口</div>
              <div className="aigc-main-subtitle">
                先做真实可访问的网站目录。点击卡片会在新窗口打开对应平台，后续再接收藏、账号备注和导入流程。
              </div>
            </div>

            <div className="aigc-content-scroll">
              <div className="aigc-grid">
                {activeCategory.platforms.map((platform) => (
                  <AigcPlatformCard key={platform.id} platform={platform} />
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
