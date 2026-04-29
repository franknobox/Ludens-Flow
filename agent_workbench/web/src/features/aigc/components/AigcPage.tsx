import React, { useEffect, useMemo, useState } from "react";
import { fetchAigcCategories } from "../api/aigc";
import type { AigcCategory, AigcPlatform } from "../types";
import { AigcCategoryPanel } from "./AigcCategoryPanel";
import { AigcPlatformCard } from "./AigcPlatformCard";
import "../styles/aigc.css";

function groupPlatforms(platforms: AigcPlatform[]) {
  const grouped = new Map<string, AigcPlatform[]>();
  for (const platform of platforms) {
    const groupName = platform.group || "全部";
    grouped.set(groupName, [...(grouped.get(groupName) || []), platform]);
  }
  return Array.from(grouped.entries()).map(([name, items]) => ({ name, items }));
}

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
  const groupedPlatforms = useMemo(
    () => groupPlatforms(activeCategory?.platforms || []),
    [activeCategory?.platforms],
  );

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
                这里收集外部 AIGC 网站入口。点击卡片会在新窗口打开对应平台，后续再补收藏、备注和项目内引用流程。
              </div>
            </div>

            <div className="aigc-content-scroll">
              {groupedPlatforms.map((group) => (
                <section key={group.name} className="aigc-platform-group">
                  {groupedPlatforms.length > 1 && <h3 className="aigc-group-title">{group.name}</h3>}
                  <div className="aigc-grid">
                    {group.items.map((platform) => (
                      <AigcPlatformCard key={platform.id} platform={platform} />
                    ))}
                  </div>
                </section>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
