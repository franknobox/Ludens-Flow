export interface AigcPlatform {
  id: string;
  name: string;
  description: string;
  category: string;
  group?: string;
  url: string;
  supported_types: string[];
  status: "online" | "maintenance" | "coming_soon";
  region?: "global" | "china";
  iconUrl?: string;
}

export interface AigcCategory {
  id: string;
  name: string;
  icon: string;
  platforms: AigcPlatform[];
}
