(function () {
  const RIGHT_PANEL_SELECTOR = '[data-panel="right"]';
  const CHAT_PANEL_SELECTOR = '[data-panel="chat"]';
  const AUTOSAVE_PREFIX = "ludens-flow:level-layout:auto-save:v1:";
  const SAVE_DEBOUNCE_MS = 500;
  const TOOL_GROUPS = [
    {
      match: ["矩形", "圆形", "Rectangle", "Circle"],
      options: [
        { tool: "rect", zh: "矩形", en: "Rectangle", icon: "□" },
        { tool: "circle", zh: "圆形", en: "Circle", icon: "○" },
      ],
    },
    {
      match: ["门工具", "窗工具", "描边还原", "Door Tool", "Window Tool", "Stroke Restore"],
      options: [
        { tool: "door", zh: "门工具", en: "Door Tool", icon: "D", color: "activeDoorColor" },
        { tool: "window", zh: "窗工具", en: "Window Tool", icon: "W", color: "activeWindowColor" },
        { tool: "stroke-restore", zh: "描边还原", en: "Stroke Restore", icon: "S", fixedColor: "#10A37F" },
      ],
    },
    {
      match: ["矩形直梯", "矩形回旋梯", "圆形螺旋梯", "Straight Stairs", "Switchback Stairs", "Spiral Stairs"],
      options: [
        { tool: "stairs-straight", zh: "矩形直梯", en: "Straight Stairs", icon: "↕" },
        { tool: "stairs-switchback", zh: "矩形回旋梯", en: "Switchback Stairs", icon: "U" },
        { tool: "stairs-spiral", zh: "圆形螺旋梯", en: "Spiral Stairs", icon: "O" },
      ],
    },
    {
      match: ["测量尺", "步行测量", "步行测量(寻路)", "Ruler", "Walk Measure", "Walk Measure (Pathfinding)"],
      options: [
        { tool: "ruler", zh: "测量尺", en: "Ruler", icon: "R" },
        { tool: "walk-measure", zh: "步行测量", en: "Walk Measure", icon: "P" },
      ],
    },
    {
      match: [
        "Polygon编辑",
        "添加顶点",
        "删除顶点",
        "移动顶点",
        "Polygon Edit",
        "Add Vertex",
        "Delete Vertex",
        "Move Vertex",
      ],
      options: [
        { tool: "polygon", zh: "Polygon编辑", en: "Polygon Edit", icon: "P" },
        { tool: "polygon-add", zh: "添加顶点", en: "Add Vertex", icon: "+" },
        { tool: "polygon-delete", zh: "删除顶点", en: "Delete Vertex", icon: "-" },
        { tool: "polygon-move", zh: "移动顶点", en: "Move Vertex", icon: "M" },
      ],
    },
  ];

  let autosaveStarted = false;
  let pendingSave = null;
  let lastSerializedLevel = "";
  let closeToolMenuTimer = null;
  let activeToolMenuRoot = null;

  function compactText(element) {
    return (element.textContent || "").replace(/\s+/g, "").toLowerCase();
  }

  function isAiTab(button) {
    const label = compactText(button);
    const hasSparklesIcon = Boolean(button.querySelector(".lucide-sparkles"));
    return label === "ai" || label.startsWith("ai") || (hasSparklesIcon && label.includes("ai"));
  }

  function isActiveTab(button) {
    const className = String(button.getAttribute("class") || "");
    return className.includes("border-b-2") || className.includes("text-[#10A37F]");
  }

  function stripOriginalAiPanel() {
    const rightPanel = document.querySelector(RIGHT_PANEL_SELECTOR);
    if (!rightPanel) {
      return;
    }

    const tabBar = rightPanel.firstElementChild;
    if (tabBar) {
      const buttons = Array.from(tabBar.querySelectorAll("button"));
      const settingsTab = buttons[0];

      buttons.forEach((button) => {
        if (!isAiTab(button)) {
          return;
        }
        if (isActiveTab(button) && settingsTab && settingsTab !== button) {
          settingsTab.click();
        }
        button.setAttribute("data-ludens-ai-tab", "true");
      });
    }

    rightPanel.querySelectorAll(CHAT_PANEL_SELECTOR).forEach((panel) => {
      const wrapper = panel.parentElement || panel;
      wrapper.setAttribute("data-ludens-ai-panel", "true");
    });
  }

  function getStoreState() {
    const store = window.__LUDENS_LEVEL_LAYOUT_STORE__;
    return store && typeof store.getState === "function" ? store.getState() : null;
  }

  function getToolGroupRoot(button) {
    const buttonWrap = button.parentElement;
    if (!buttonWrap || !buttonWrap.querySelector(".bottom-1.right-1")) {
      return null;
    }
    return buttonWrap.parentElement;
  }

  function getToolGroup(root) {
    const label = (root.textContent || "").replace(/\s+/g, "");
    return TOOL_GROUPS.find((group) => group.match.some((candidate) => label === candidate.replace(/\s+/g, ""))) || null;
  }

  function shouldUseChinese(root) {
    return /[\u4e00-\u9fff]/.test(root.textContent || "");
  }

  function closeToolMenu(root) {
    const targetRoot = root || activeToolMenuRoot;
    if (!targetRoot) {
      return;
    }
    targetRoot.querySelectorAll(":scope > .ludens-tool-menu").forEach((menu) => menu.remove());
    targetRoot.removeAttribute("data-ludens-tool-menu-open");
    if (activeToolMenuRoot === targetRoot) {
      activeToolMenuRoot = null;
    }
  }

  function scheduleCloseToolMenu(root) {
    if (closeToolMenuTimer) {
      window.clearTimeout(closeToolMenuTimer);
    }
    closeToolMenuTimer = window.setTimeout(() => {
      closeToolMenuTimer = null;
      closeToolMenu(root);
    }, 140);
  }

  function cancelCloseToolMenu() {
    if (closeToolMenuTimer) {
      window.clearTimeout(closeToolMenuTimer);
      closeToolMenuTimer = null;
    }
  }

  function showToolMenu(root, group) {
    const state = getStoreState();
    if (!state || typeof state.setActiveTool !== "function") {
      return;
    }

    cancelCloseToolMenu();
    if (activeToolMenuRoot && activeToolMenuRoot !== root) {
      closeToolMenu(activeToolMenuRoot);
    }
    closeToolMenu(root);
    activeToolMenuRoot = root;
    root.setAttribute("data-ludens-tool-menu-open", "true");

    const useChinese = shouldUseChinese(root);
    const menu = document.createElement("div");
    menu.className = "ludens-tool-menu";
    menu.addEventListener("mouseenter", cancelCloseToolMenu);
    menu.addEventListener("mouseleave", () => scheduleCloseToolMenu(root));
    menu.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      event.stopPropagation();
    });

    group.options.forEach((option) => {
      const item = document.createElement("button");
      item.type = "button";
      item.dataset.tool = option.tool;
      if (state.activeTool === option.tool) {
        item.dataset.active = "true";
      }

      const icon = document.createElement("span");
      icon.className = "ludens-tool-menu-icon";
      icon.textContent = option.icon;

      const label = document.createElement("span");
      label.textContent = useChinese ? option.zh : option.en;

      item.append(icon, label);
      const dotColor = option.fixedColor || (option.color ? state[option.color] : "");
      if (dotColor) {
        const dot = document.createElement("span");
        dot.className = "ludens-tool-menu-dot";
        dot.style.backgroundColor = dotColor;
        item.append(dot);
      }

      item.addEventListener("mouseenter", () => {
        menu.querySelectorAll("[data-hovered]").forEach((node) => node.removeAttribute("data-hovered"));
        item.dataset.hovered = "true";
      });
      item.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        state.setActiveTool(option.tool);
        closeToolMenu(root);
      });
      menu.append(item);
    });

    root.append(menu);
  }

  function bindToolbarHoverMenus() {
    document.querySelectorAll("button").forEach((button) => {
      const root = getToolGroupRoot(button);
      if (!root || root.dataset.ludensToolMenuBound === "true") {
        return;
      }

      const group = getToolGroup(root);
      if (!group) {
        return;
      }

      root.dataset.ludensToolMenuBound = "true";
      root.addEventListener("mouseenter", () => showToolMenu(root, group));
      root.addEventListener("mouseleave", () => scheduleCloseToolMenu(root));
    });
  }

  function getProjectId() {
    try {
      const params = new URLSearchParams(window.location.search);
      return params.get("ludensProjectId") || "default";
    } catch {
      return "default";
    }
  }

  function getAutosaveKey() {
    return AUTOSAVE_PREFIX + getProjectId();
  }

  function isPersistableLevel(level) {
    return Boolean(
      level &&
        typeof level === "object" &&
        Array.isArray(level.shapes) &&
        Array.isArray(level.entities) &&
        Array.isArray(level.layers),
    );
  }

  function serializeLevel(level) {
    if (!isPersistableLevel(level)) {
      return "";
    }
    try {
      return JSON.stringify(level);
    } catch {
      return "";
    }
  }

  function readSavedLevel() {
    try {
      const raw = localStorage.getItem(getAutosaveKey());
      if (!raw) {
        return null;
      }
      const payload = JSON.parse(raw);
      return isPersistableLevel(payload && payload.level) ? payload.level : null;
    } catch {
      return null;
    }
  }

  function writeSavedLevel(level) {
    const serialized = serializeLevel(level);
    if (!serialized || serialized === lastSerializedLevel) {
      return;
    }
    try {
      localStorage.setItem(
        getAutosaveKey(),
        JSON.stringify({
          version: 1,
          projectId: getProjectId(),
          savedAt: new Date().toISOString(),
          level: JSON.parse(serialized),
        }),
      );
      lastSerializedLevel = serialized;
    } catch (error) {
      console.warn("[Ludens-Flow] Failed to autosave Level Layout Studio state.", error);
    }
  }

  function scheduleSavedLevel(level) {
    if (pendingSave) {
      window.clearTimeout(pendingSave);
    }
    pendingSave = window.setTimeout(() => {
      pendingSave = null;
      writeSavedLevel(level);
    }, SAVE_DEBOUNCE_MS);
  }

  function restoreSavedLevel(store) {
    const savedLevel = readSavedLevel();
    if (!savedLevel) {
      return;
    }

    const state = store.getState();
    const currentSerialized = serializeLevel(state.level);
    const savedSerialized = serializeLevel(savedLevel);
    if (!savedSerialized || currentSerialized === savedSerialized) {
      lastSerializedLevel = savedSerialized;
      return;
    }

    if (typeof state.setLevel === "function") {
      state.setLevel(savedLevel);
    } else if (typeof store.setState === "function") {
      store.setState({ level: savedLevel, polygonData: savedLevel.polygonData || [] });
    }
    lastSerializedLevel = savedSerialized;
  }

  function startAutosave() {
    if (autosaveStarted) {
      return;
    }

    const store = window.__LUDENS_LEVEL_LAYOUT_STORE__;
    if (!store || typeof store.getState !== "function" || typeof store.subscribe !== "function") {
      return;
    }

    autosaveStarted = true;
    restoreSavedLevel(store);

    const state = store.getState();
    lastSerializedLevel = serializeLevel(state.level);

    store.subscribe((nextState) => {
      scheduleSavedLevel(nextState.level);
    });

    window.addEventListener("beforeunload", () => {
      if (pendingSave) {
        window.clearTimeout(pendingSave);
        pendingSave = null;
      }
      writeSavedLevel(store.getState().level);
    });
  }

  function start() {
    stripOriginalAiPanel();
    bindToolbarHoverMenus();
    startAutosave();
    const observer = new MutationObserver(() => {
      stripOriginalAiPanel();
      bindToolbarHoverMenus();
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
