export interface DesignCopywritingExternalReference {
  kind?: "file";
  name: string;
  mime_type?: string;
  size?: number;
  data_url: string;
}

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
  external_references?: DesignCopywritingExternalReference[];
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
  content_chars?: number;
}

export interface DesignCopywritingContext {
  project_id: string;
  artifacts: DesignCopywritingContextItem[];
  external_files: DesignCopywritingContextItem[];
  characters: DesignCopywritingContextItem[];
  terms: DesignCopywritingContextItem[];
  constraints: DesignCopywritingContextItem[];
}

export interface DesignCopywritingTable {
  kind: string;
  columns: string[];
  rows: Record<string, string>[];
}

export interface DesignCopywritingResponse {
  status: "mock" | "generated";
  request: Required<DesignCopywritingRequest>;
  candidates: DesignCopywritingCandidate[];
  table: DesignCopywritingTable | null;
  context: DesignCopywritingContext | null;
  prompt_preview?: string;
}
