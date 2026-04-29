import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { workbenchApi } from "../api";
import type {
  ProjectCreateResponse,
  ProjectMeta,
  ProjectsResponse,
  StateResponse,
  WorkbenchEvent,
} from "../types";

type ProjectEventListener = (event: WorkbenchEvent) => void;

type RuntimeProjects = {
  projects: ProjectMeta[];
  activeProjects: ProjectMeta[];
  archivedProjects: ProjectMeta[];
};

type ProjectRuntimeContextValue = RuntimeProjects & {
  runtimeState: StateResponse | null;
  loading: boolean;
  refreshRuntime: () => Promise<void>;
  selectProject: (projectId: string) => Promise<void>;
  createProject: (title: string) => Promise<void>;
  subscribeEvents: (listener: ProjectEventListener) => () => void;
};

const ProjectRuntimeContext = createContext<ProjectRuntimeContextValue | null>(null);

function toRuntimeProjects(payload: ProjectsResponse): RuntimeProjects {
  const projects = payload.projects || [];
  return {
    projects,
    activeProjects: payload.active_projects || projects,
    archivedProjects: payload.archived_projects || [],
  };
}

function toRuntimeProjectsFromCreate(
  payload: ProjectCreateResponse,
  prev: RuntimeProjects,
): RuntimeProjects {
  const nextProjects = [
    payload.project,
    ...prev.projects.filter((item) => item.id !== payload.project.id),
  ];
  const nextActiveProjects = [
    payload.project,
    ...prev.activeProjects.filter((item) => item.id !== payload.project.id),
  ];
  const nextArchivedProjects = prev.archivedProjects.filter(
    (item) => item.id !== payload.project.id,
  );
  return {
    projects: nextProjects,
    activeProjects: nextActiveProjects,
    archivedProjects: nextArchivedProjects,
  };
}

export function ProjectRuntimeProvider({ children }: { children: ReactNode }) {
  const [runtimeState, setRuntimeState] = useState<StateResponse | null>(null);
  const [projectsState, setProjectsState] = useState<RuntimeProjects>({
    projects: [],
    activeProjects: [],
    archivedProjects: [],
  });
  const [loading, setLoading] = useState(true);
  const listenersRef = useRef(new Set<ProjectEventListener>());

  const refreshRuntime = async () => {
    const [nextState, nextProjects] = await Promise.all([
      workbenchApi.getState(),
      workbenchApi.getProjects(),
    ]);
    setRuntimeState(nextState);
    setProjectsState(toRuntimeProjects(nextProjects));
  };

  const selectProject = async (projectId: string) => {
    if (!projectId) {
      return;
    }
    const selected = await workbenchApi.selectProject(projectId);
    setRuntimeState(selected.state);
    const projectsPayload = await workbenchApi.getProjects();
    setProjectsState(toRuntimeProjects(projectsPayload));
  };

  const createProject = async (title: string) => {
    const trimmed = title.trim();
    if (!trimmed) {
      throw new Error("Project title cannot be empty.");
    }
    const created = await workbenchApi.createProject({
      display_name: trimmed,
      title: trimmed,
    });
    setRuntimeState(created.state);
    setProjectsState((prev) => toRuntimeProjectsFromCreate(created, prev));
    const projectsPayload = await workbenchApi.getProjects();
    setProjectsState(toRuntimeProjects(projectsPayload));
  };

  useEffect(() => {
    let active = true;
    void (async () => {
      setLoading(true);
      try {
        await refreshRuntime();
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const projectId = runtimeState?.project_id;
    if (!projectId) {
      return;
    }

    const source = workbenchApi.openProjectEvents(projectId, (event) => {
      const shouldApplyState =
        event.type === "connected" ||
        event.type === "run_started" ||
        event.type === "state_updated" ||
        event.type === "run_failed";
      if (event.state && shouldApplyState) {
        setRuntimeState(event.state);
      }

      if (
        event.type === "connected" ||
        event.type === "state_updated" ||
        event.type === "run_failed" ||
        event.type === "projects_updated"
      ) {
        setProjectsState((prev) => ({
          projects: event.projects || prev.projects,
          activeProjects: event.active_projects || event.projects || prev.activeProjects,
          archivedProjects: event.archived_projects || prev.archivedProjects,
        }));
      }

      listenersRef.current.forEach((listener) => {
        listener(event);
      });
    });

    return () => {
      source.close();
    };
  }, [runtimeState?.project_id]);

  const subscribeEvents = (listener: ProjectEventListener) => {
    listenersRef.current.add(listener);
    return () => {
      listenersRef.current.delete(listener);
    };
  };

  const value = useMemo<ProjectRuntimeContextValue>(
    () => ({
      runtimeState,
      loading,
      projects: projectsState.projects,
      activeProjects: projectsState.activeProjects,
      archivedProjects: projectsState.archivedProjects,
      refreshRuntime,
      selectProject,
      createProject,
      subscribeEvents,
    }),
    [loading, projectsState, runtimeState],
  );

  return (
    <ProjectRuntimeContext.Provider value={value}>
      {children}
    </ProjectRuntimeContext.Provider>
  );
}

export function useProjectRuntime() {
  const context = useContext(ProjectRuntimeContext);
  if (!context) {
    throw new Error("useProjectRuntime must be used inside ProjectRuntimeProvider");
  }
  return context;
}
