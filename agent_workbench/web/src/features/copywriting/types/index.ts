export interface DesignCopywritingRequest {
  copy_type: string;
  brief?: string;
  purpose?: string;
  quantity?: number;
  style?: string;
  length?: string;
  must_include?: string[];
  must_avoid?: string[];
  reference_ids?: string[];
  language?: string;
}

export interface DesignCopywritingCandidate {
  id: string;
  text: string;
  notes: string[];
  tags: string[];
}

export interface DesignCopywritingContextItem {
  id: string;
  name: string;
  source: string;
  content: string;
}

export interface DesignCopywritingContext {
  project_id: string;
  artifacts: DesignCopywritingContextItem[];
  characters: DesignCopywritingContextItem[];
  terms: DesignCopywritingContextItem[];
  constraints: DesignCopywritingContextItem[];
}

export interface DesignCopywritingResponse {
  status: "mock" | "generated";
  request: Required<DesignCopywritingRequest>;
  candidates: DesignCopywritingCandidate[];
  context: DesignCopywritingContext | null;
  prompt_preview: string;
}
