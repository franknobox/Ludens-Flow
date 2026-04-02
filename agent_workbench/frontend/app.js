(function () {
  const {
    getState,
    getProjects,
    getWorkspaceFiles,
    getWorkspaceFileContent,
    postChat,
    createProject: createProjectRequest,
    selectProject: selectProjectRequest,
    resetCurrentProject,
  } = window.WorkbenchApi;

  const AGENTS = [
    { key: "design", name: "Dam / Design" },
    { key: "pm", name: "Pax / PM" },
    { key: "engineering", name: "Eon / Engineering" },
    { key: "review", name: "Revs / Review" },
  ];

  const phaseLabel = {
    GDD_DISCUSS: "GDD Discuss",
    GDD_COMMIT: "GDD Commit",
    PM_DISCUSS: "PM Discuss",
    PM_COMMIT: "PM Commit",
    ENG_DISCUSS: "ENG Discuss",
    ENG_COMMIT: "ENG Commit",
    REVIEW: "Review",
    POST_REVIEW_DECISION: "Post Review Decision",
    DEV_COACHING: "Dev Coaching",
  };

  const stateModel = {
    project_id: "",
    phase: "",
    current_agent: "design",
    iteration_count: 0,
    artifact_frozen: false,
    review_gate: null,
    transcript_history: [],
    chat_history: [],
    files: [],
    projects: [],
  };

  const historyByAgent = { design: [], pm: [], engineering: [], review: [] };
  const fileCache = {};

  let currentView = { type: "agent", id: "design" };
  let pendingImages = [];
  let requestInFlight = false;
  let transientChat = null;
  let sidebarMode = "projects";

  const el = (id) => document.getElementById(id);
  const esc = (text) => String(text || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const agentName = (key) => (AGENTS.find((agent) => agent.key === key) || {}).name || key;
  const phaseToAgent = (phase) => {
    if (!phase) return "design";
    if (phase.startsWith("GDD_")) return "design";
    if (phase.startsWith("PM_")) return "pm";
    if (phase.startsWith("ENG_") || phase === "DEV_COACHING") return "engineering";
    return "review";
  };
  const readonly = () => currentView.type !== "agent" || currentView.id !== stateModel.current_agent;
  const projectMeta = () => stateModel.projects.find((project) => project.id === stateModel.project_id);
  const projectName = () => (projectMeta() || {}).display_name || stateModel.project_id || "Project";
  const projectUpdated = (project) => project && project.updated_at ? String(project.updated_at).replace("T", " ").replace("Z", "") : "No activity";

  function normalizeAgent(agent, phase) {
    const raw = String(agent || "").toLowerCase();
    if (raw.includes("design")) return "design";
    if (raw.includes("pm")) return "pm";
    if (raw.includes("engineer")) return "engineering";
    if (raw.includes("review")) return "review";
    return phaseToAgent(phase);
  }

  function rebuildHistory() {
    Object.keys(historyByAgent).forEach((key) => {
      historyByAgent[key] = [];
    });

    const transcript = stateModel.transcript_history || [];
    if (transcript.length) {
      transcript.forEach((item) => {
        const key = normalizeAgent(item.agent, item.phase);
        if (historyByAgent[key]) {
          historyByAgent[key].push({
            role: item.role,
            content: String(item.content || ""),
            phase: item.phase || stateModel.phase,
          });
        }
      });
      return;
    }

    const key = stateModel.current_agent || phaseToAgent(stateModel.phase);
    (stateModel.chat_history || []).forEach((item) => {
      historyByAgent[key].push({
        role: item.role,
        content: String(item.content || ""),
        phase: stateModel.phase,
      });
    });
  }

  function transientMessageText(text, imageCount) {
    const clean = String(text || "").trim();
    if (clean && imageCount) return `${clean}\n[${imageCount} image${imageCount > 1 ? "s" : ""}]`;
    if (clean) return clean;
    if (imageCount) return `[${imageCount} image${imageCount > 1 ? "s" : ""}]`;
    return "";
  }

  function scrollContentToBottom() {
    requestAnimationFrame(() => {
      const area = el("contentArea");
      if (area) area.scrollTop = area.scrollHeight;
    });
  }

  function itemHtml(title, tag, sub) {
    return `<div class="item-title"><span>${esc(title)}</span><span class="tag ${tag === "ACTIVE" ? "active" : ""}">${tag}</span></div><div class="item-sub">${esc(sub || "")}</div>`;
  }

  function projectCardHtml(project) {
    const tag = project.id === stateModel.project_id ? "ACTIVE" : (project.archived ? "ARCHIVED" : "OPEN");
    const phase = project.last_phase || "No phase yet";
    const preview = project.last_message_preview || "No assistant message yet";
    return `
      <div class="item-title"><span>${esc(project.display_name || project.id)}</span><span class="tag ${tag === "ACTIVE" ? "active" : ""}">${esc(tag)}</span></div>
      <div class="item-sub">${esc(project.id)} · ${esc(phase)}</div>
      <div class="item-sub">${esc(projectUpdated(project))}</div>
      <div class="item-sub preview">${esc(preview)}</div>
    `;
  }

  function renderProjects() {
    const list = el("projectList");
    list.innerHTML = "";
    if (!stateModel.projects.length) {
      list.innerHTML = `<div class="empty">No projects yet.</div>`;
      return;
    }

    stateModel.projects.forEach((project) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "item" + (project.id === stateModel.project_id ? " active" : "");
      button.innerHTML = projectCardHtml(project);
      button.onclick = () => openProject(project.id);
      list.appendChild(button);
    });
  }

  function renderFiles() {
    const list = el("fileList");
    list.innerHTML = "";
    stateModel.files.forEach((file) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "item" + (currentView.type === "file" && currentView.id === file.id ? " active" : "");
      button.innerHTML = itemHtml(file.name, "FILE", "Project-local artifact");
      button.onclick = () => {
        currentView = { type: "file", id: file.id };
        renderAll();
        loadFileContent(file.id);
      };
      list.appendChild(button);
    });
  }

  function renderAgents() {
    const list = el("agentList");
    list.innerHTML = "";
    AGENTS.forEach((agent) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "item" + (currentView.type === "agent" && currentView.id === agent.key ? " active" : "");
      button.innerHTML = itemHtml(
        agent.name,
        agent.key === stateModel.current_agent ? "CURRENT" : "HISTORY",
        agent.key === stateModel.current_agent ? "Writable now" : "Read-only transcript"
      );
      button.onclick = () => {
        currentView = { type: "agent", id: agent.key };
        renderAll();
      };
      list.appendChild(button);
    });
  }

  function renderMessageRow(agentKey, item) {
    const user = item.role === "user";
    const sender = user ? "You" : agentName(agentKey);
    const avatar = user ? "ME" : sender.slice(0, 1).toUpperCase();
    const bubble = item.thinking
      ? `<div class="bubble thinking"><span>Thinking</span><span class="thinking-dots"><span></span><span></span><span></span></span></div>`
      : `<div class="bubble">${esc(item.content)}</div>`;
    return `<div class="msg ${user ? "user" : "agent"}"><div class="avatar">${esc(avatar)}</div><div><div class="sender">${esc(sender)} · ${esc(item.phase || "")}</div>${bubble}</div></div>`;
  }

  function renderMessages(agentKey) {
    const rows = [...(historyByAgent[agentKey] || [])];
    if (transientChat && transientChat.agentKey === agentKey) {
      rows.push({ role: "user", content: transientChat.userText, phase: transientChat.phase });
      if (transientChat.thinking) {
        rows.push({ role: "assistant", content: "", phase: transientChat.phase, thinking: true });
      }
    }

    if (!rows.length) {
      return `<div class="empty">No conversation yet for ${esc(agentName(agentKey))} in this project.</div>`;
    }

    return `<div class="messages">${rows.map((item) => renderMessageRow(agentKey, item)).join("")}</div>`;
  }

  function renderFile(fileId) {
    const file = stateModel.files.find((item) => item.id === fileId);
    const content = fileCache[fileId];
    return `<div class="file-panel"><div class="file-title">${esc((file || {}).name || fileId)}</div><pre class="file-content">${typeof content === "string" ? esc(content || "(empty)") : "Loading..."}</pre></div>`;
  }

  function renderMain() {
    const title = currentView.type === "agent"
      ? agentName(currentView.id)
      : ((stateModel.files.find((file) => file.id === currentView.id) || {}).name || currentView.id);
    const subtitle = currentView.type === "agent"
      ? `Current project: ${projectName()} · Active agent: ${agentName(stateModel.current_agent)}`
      : `Viewing artifact inside ${projectName()}`;

    el("mainTitle").textContent = title;
    el("mainSubtitle").textContent = subtitle;
    el("projectBadge").textContent = projectName();
    el("phaseBadge").textContent = phaseLabel[stateModel.phase] || stateModel.phase || "-";
    el("modeBadge").textContent = currentView.type === "agent" ? "Agent Chat" : "File Viewer";
    el("readonlyBadge").style.display = currentView.type === "agent" && readonly() ? "inline-flex" : "none";
    if (readonly()) {
      el("readonlyBadge").textContent = `Read Only · ${agentName(stateModel.current_agent)}`;
    }

    el("contentArea").innerHTML = currentView.type === "agent" ? renderMessages(currentView.id) : renderFile(currentView.id);
    el("composer").style.display = currentView.type === "agent" ? "block" : "none";
    el("input").disabled = readonly() || requestInFlight;
    el("sendBtn").disabled = readonly() || requestInFlight;
    el("attachBtn").disabled = readonly() || requestInFlight;
    el("input").placeholder = readonly()
      ? `Read-only history. Current active agent is ${agentName(stateModel.current_agent)}.`
      : `Talk to ${agentName(currentView.id)} inside ${projectName()}...`;
    el("decisionBar").style.display = stateModel.phase === "POST_REVIEW_DECISION" && !readonly() ? "block" : "none";

    if (currentView.type === "agent") {
      scrollContentToBottom();
    }
  }

  function renderStatus() {
    el("statusProject").textContent = projectName();
    el("statusAgent").textContent = agentName(stateModel.current_agent);
    el("statusPhase").textContent = phaseLabel[stateModel.phase] || stateModel.phase || "-";
    el("statusIterations").textContent = `${stateModel.iteration_count || 0}`;
    el("statusFiles").textContent = `${stateModel.files.length} files`;
    el("statusMode").textContent = readonly() ? "Read-only view" : "Writable";
    el("statusUpdated").textContent = projectUpdated(projectMeta());
    el("statusLastPhase").textContent = (projectMeta() || {}).last_phase || "-";

    if ((projectMeta() || {}).archived) {
      el("statusNote").textContent = "Current project is archived. You can still inspect its local state and artifacts.";
    } else if (stateModel.artifact_frozen) {
      el("statusNote").textContent = "Current project is in DEV_COACHING. Canonical artifacts are frozen.";
    } else if ((projectMeta() || {}).last_message_preview) {
      el("statusNote").textContent = (projectMeta() || {}).last_message_preview;
    } else {
      el("statusNote").textContent = "Current project is writable. State, artifacts, profile and logs stay inside this project.";
    }
  }

  function renderSidebar() {
    const inProject = sidebarMode === "project";
    el("sidebarTitle").textContent = inProject ? projectName() : "Workspace";
    el("sidebarBackBtn").style.display = inProject ? "inline-flex" : "none";
    el("sidebarProjectsPanel").style.display = inProject ? "none" : "block";
    el("sidebarProjectPanel").style.display = inProject ? "block" : "none";
    el("resetBtn").style.display = inProject ? "inline-flex" : "none";
  }

  function renderAll() {
    renderSidebar();
    renderProjects();
    renderFiles();
    renderAgents();
    renderMain();
    renderStatus();
  }

  function setError(message) {
    el("errorText").textContent = message || "";
  }

  async function loadStateIntoModel() {
    const state = await getState();
    stateModel.project_id = state.project_id || "";
    stateModel.phase = state.phase || "";
    stateModel.current_agent = state.current_agent || phaseToAgent(state.phase);
    stateModel.iteration_count = state.iteration_count || 0;
    stateModel.artifact_frozen = !!state.artifact_frozen;
    stateModel.review_gate = state.review_gate || null;
    stateModel.transcript_history = state.transcript_history || [];
    stateModel.chat_history = state.chat_history || [];
    rebuildHistory();
  }

  async function loadProjectsIntoModel() {
    const data = await getProjects();
    stateModel.projects = data.projects || [];
  }

  async function loadFilesIntoModel() {
    const data = await getWorkspaceFiles();
    stateModel.files = data.files || [];
  }

  async function loadFileContent(fileId) {
    try {
      const data = await getWorkspaceFileContent(fileId);
      fileCache[fileId] = data.content || "";
    } catch (error) {
      fileCache[fileId] = `Load failed: ${error.message}`;
    }

    if (currentView.type === "file" && currentView.id === fileId) {
      renderMain();
    }
  }

  async function refreshFileCache() {
    Object.keys(fileCache).forEach((key) => delete fileCache[key]);
    await Promise.all(stateModel.files.map((file) => loadFileContent(file.id)));
  }

  async function hardRefresh() {
    await loadStateIntoModel();
    await loadProjectsIntoModel();
    await loadFilesIntoModel();
    await refreshFileCache();
    currentView = { type: "agent", id: stateModel.current_agent };
    renderAll();
  }

  function readAsDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  function renderThumbs() {
    const wrap = el("attachments");
    const box = el("thumbs");
    box.innerHTML = "";

    pendingImages.forEach((dataUrl, index) => {
      const div = document.createElement("div");
      div.className = "thumb";
      div.innerHTML = `<img src="${dataUrl}" alt=""><button type="button" class="remove">x</button>`;
      div.querySelector(".remove").onclick = () => {
        pendingImages.splice(index, 1);
        renderThumbs();
      };
      box.appendChild(div);
    });

    wrap.style.display = pendingImages.length ? "flex" : "none";
  }

  async function createProject() {
    const projectId = el("projectIdInput").value.trim();
    const title = el("projectTitleInput").value.trim();
    if (!projectId) {
      setError("Project id is required.");
      return;
    }

    setError("");
    try {
      await createProjectRequest({
        project_id: projectId,
        display_name: title || null,
      });
      el("projectIdInput").value = "";
      el("projectTitleInput").value = "";
      sidebarMode = "project";
      await hardRefresh();
    } catch (error) {
      setError("Create project failed: " + error.message);
    }
  }

  async function selectProject(projectId) {
    if (!projectId || projectId === stateModel.project_id) return;

    setError("");
    transientChat = null;
    try {
      await selectProjectRequest(projectId);
      await hardRefresh();
    } catch (error) {
      setError("Switch project failed: " + error.message);
    }
  }

  async function openProject(projectId) {
    if (!projectId) return;
    sidebarMode = "project";
    if (projectId === stateModel.project_id) {
      renderAll();
      return;
    }
    await selectProject(projectId);
  }

  async function sendMessage(message) {
    if (currentView.type !== "agent" || readonly()) return;

    const text = String(message || "").trim();
    if (!text && !pendingImages.length) return;

    setError("");
    requestInFlight = true;
    const body = { message: text };
    if (pendingImages.length) {
      body.images = pendingImages.slice();
    }

    transientChat = {
      agentKey: currentView.id,
      phase: stateModel.phase,
      userText: transientMessageText(text, pendingImages.length),
      thinking: true,
    };

    pendingImages = [];
    renderThumbs();
    el("input").value = "";
    renderAll();

    try {
      const response = await postChat(body);
      if (response.error) {
        setError(response.error);
      }
      transientChat = null;
      await loadStateIntoModel();
      await loadProjectsIntoModel();
      await loadFilesIntoModel();
      await refreshFileCache();
      renderAll();
    } catch (error) {
      if (transientChat) {
        transientChat.thinking = false;
      }
      setError("Request failed: " + error.message);
      renderAll();
    } finally {
      requestInFlight = false;
      renderAll();
    }
  }

  async function resetProject() {
    if (!confirm(`Reset ${projectName()}?\n\nThis clears the current project's state, artifacts, and images.`)) return;

    await resetCurrentProject();
    pendingImages = [];
    transientChat = null;
    renderThumbs();
    setError("");
    await hardRefresh();
  }

  function bindEvents() {
    el("createProjectBtn").addEventListener("click", createProject);
    el("refreshBtn").addEventListener("click", hardRefresh);
    el("resetBtn").addEventListener("click", resetProject);
    el("sidebarBackBtn").addEventListener("click", () => {
      sidebarMode = "projects";
      renderAll();
    });
    el("sendBtn").addEventListener("click", () => sendMessage(el("input").value));
    el("input").addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendMessage(el("input").value);
      }
    });
    el("attachBtn").addEventListener("click", () => el("fileInput").click());
    el("fileInput").addEventListener("change", async function () {
      const files = Array.from(this.files || []);
      this.value = "";
      for (const file of files) {
        if (!file.type.startsWith("image/")) continue;
        try {
          pendingImages.push(await readAsDataUrl(file));
        } catch (_) {}
      }
      renderThumbs();
    });
    el("decisionBar").querySelectorAll("button[data-choice]").forEach((button) => {
      button.addEventListener("click", () => sendMessage(button.dataset.choice));
    });
  }

  async function init() {
    bindEvents();
    await hardRefresh();
  }

  init();
})();
