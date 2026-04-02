(function () {
  const API = "";

  async function fetchJson(path, options) {
    const response = await fetch(API + path, options);
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || data.error || `Request failed: ${response.status}`);
    }
    return data;
  }

  window.WorkbenchApi = {
    getState() {
      return fetchJson("/api/state");
    },

    getProjects() {
      return fetchJson("/api/projects");
    },

    getWorkspaceFiles() {
      return fetchJson("/api/workspace/files");
    },

    getWorkspaceFileContent(fileId) {
      return fetchJson(`/api/workspace/files/${encodeURIComponent(fileId)}/content`);
    },

    postChat(body) {
      return fetchJson("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    },

    createProject(body) {
      return fetchJson("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    },

    selectProject(projectId) {
      return fetchJson(`/api/projects/${encodeURIComponent(projectId)}/select`, {
        method: "POST",
      });
    },

    resetCurrentProject() {
      return fetchJson("/api/projects/current/reset", {
        method: "POST",
      });
    },
  };
})();
