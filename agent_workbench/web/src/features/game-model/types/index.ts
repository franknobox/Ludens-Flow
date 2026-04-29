export type ModelCategory = "npc" | "quest" | "narrative" | "worldbuilding" | "voice" | "image";

export interface GameModel {
  id: string;
  name: string;
  provider: string;
  description: string;
  categories: ModelCategory[];
  contextWindow: number;
  strengths: string[];
  inputCostPer1M: number;
  outputCostPer1M: number;
  status: "recommended" | "popular" | "coming_soon";
  recommendedFor: string[];
}

export interface CustomModelConfig {
  name: string;
  baseUrl: string;
  apiKey: string;
  modelName: string;
}

export interface GameSceneConfig {
  id: string;
  name: string;
  category: "npc" | "quest" | "narrative" | "worldbuilding" | "voice" | "image";
  modelId: string;
  systemPrompt: string;
  temperature: number;
  maxTokens: number;
  tools: string[];
  testInput: string;
  testOutput?: string;
}

export interface ExportConfig {
  sceneId: string;
  sceneName: string;
  modelId: string;
  modelName: string;
  endpoint: string;
  runtimeParams: {
    temperature: number;
    maxTokens: number;
    tools: string[];
  };
  unitySnippet: string;
}

export const MODEL_CATEGORIES: { id: ModelCategory; label: string; icon: string; hint: string }[] = [
  { id: "npc", label: "NPC 对话", icon: "💬", hint: "角色对话、语音 NPC" },
  { id: "quest", label: "任务生成", icon: "📋", hint: "任务设计、奖励生成" },
  { id: "narrative", label: "剧情叙事", icon: "📖", hint: "剧情分支、对话树" },
  { id: "worldbuilding", label: "世界观构建", icon: "🌍", hint: "背景设定、物品描述" },
  { id: "voice", label: "语音合成", icon: "🎙️", hint: "TTS、情感配音" },
  { id: "image", label: "图像生成", icon: "🎨", hint: "角色立绘、场景图" },
];

export const MOCK_MODELS: GameModel[] = [
  {
    id: "gpt-4o",
    name: "GPT-4o",
    provider: "OpenAI",
    description: "全能型模型，适合 NPC 对话、任务生成、剧情叙事等多种场景。",
    categories: ["npc", "quest", "narrative"],
    contextWindow: 128000,
    strengths: ["多用途", "强推理", "上下文充足"],
    inputCostPer1M: 5,
    outputCostPer1M: 15,
    status: "recommended",
    recommendedFor: ["NPC 多轮对话", "动态任务生成", "分支剧情"],
  },
  {
    id: "gpt-4o-mini",
    name: "GPT-4o Mini",
    provider: "OpenAI",
    description: "轻量快速，适合频繁调用的简单场景。",
    categories: ["npc", "quest"],
    contextWindow: 128000,
    strengths: ["低成本", "低延迟"],
    inputCostPer1M: 0.15,
    outputCostPer1M: 0.6,
    status: "popular",
    recommendedFor: ["简单 NPC 回复", "快速生成任务描述"],
  },
  {
    id: "claude-3.5-sonnet",
    name: "Claude 3.5 Sonnet",
    provider: "Anthropic",
    description: "擅长长文本和复杂叙事生成，适合剧情和世界观构建。",
    categories: ["narrative", "worldbuilding", "npc"],
    contextWindow: 200000,
    strengths: ["长文本强", "叙事质量高", "角色一致"],
    inputCostPer1M: 3,
    outputCostPer1M: 15,
    status: "recommended",
    recommendedFor: ["分支剧情生成", "世界观构建", "角色扮演对话"],
  },
  {
    id: "o1",
    name: "o1 (推理)",
    provider: "OpenAI",
    description: "强推理模型，适合需要复杂逻辑的关卡设计和任务树生成。",
    categories: ["quest", "narrative"],
    contextWindow: 65536,
    strengths: ["强推理", "复杂逻辑"],
    inputCostPer1M: 15,
    outputCostPer1M: 60,
    status: "popular",
    recommendedFor: ["关卡逻辑设计", "任务树生成", "谜题设计"],
  },
  {
    id: "gemini-2.0-flash",
    name: "Gemini 2.0 Flash",
    provider: "Google",
    description: "快速响应，适合实时 NPC 互动和语音合成前处理。",
    categories: ["npc", "voice"],
    contextWindow: 1000000,
    strengths: ["超长上下文", "免费额度大"],
    inputCostPer1M: 0,
    outputCostPer1M: 0,
    status: "recommended",
    recommendedFor: ["实时 NPC", "大规模世界观查询"],
  },
  {
    id: "dall-e-3",
    name: "DALL-E 3",
    provider: "OpenAI",
    description: "高质量图像生成，适合角色立绘、场景概念图。",
    categories: ["image"],
    contextWindow: 0,
    strengths: ["高质量图像", "风格控制"],
    inputCostPer1M: 0,
    outputCostPer1M: 0,
    status: "recommended",
    recommendedFor: ["角色立绘", "场景概念图", "UI 背景"],
  },
  {
    id: "elevenlabs",
    name: "ElevenLabs",
    provider: "ElevenLabs",
    description: "高质量语音合成，支持情感控制和多种语言。",
    categories: ["voice"],
    contextWindow: 0,
    strengths: ["自然语音", "多语言", "情感控制"],
    inputCostPer1M: 0,
    outputCostPer1M: 0,
    status: "popular",
    recommendedFor: ["NPC 语音", "旁白配音", "多语言支持"],
  },
  {
    id: "o3",
    name: "o3-mini",
    provider: "OpenAI",
    description: "均衡型模型，适合综合游戏内容生成。",
    categories: ["npc", "quest", "narrative", "worldbuilding"],
    contextWindow: 200000,
    strengths: ["均衡", "性价比高"],
    inputCostPer1M: 0,
    outputCostPer1M: 0,
    status: "popular",
    recommendedFor: ["综合内容生成", "混合场景"],
  },
  {
    id: "gemini-2.5-pro",
    name: "Gemini 2.5 Pro",
    provider: "Google",
    description: "长上下文强，适合大型世界观管理和复杂剧情分支。",
    categories: ["worldbuilding", "narrative"],
    contextWindow: 1000000,
    strengths: ["超长上下文", "复杂叙事"],
    inputCostPer1M: 1.25,
    outputCostPer1M: 10,
    status: "popular",
    recommendedFor: ["大型世界观", "剧情分支管理", "多章节叙事"],
  },
  {
    id: "suno",
    name: "Suno AI",
    provider: "Suno",
    description: "音乐生成，适合游戏背景音乐和主题音乐创作。",
    categories: ["voice"],
    contextWindow: 0,
    strengths: ["音乐生成", "多风格"],
    inputCostPer1M: 0,
    outputCostPer1M: 0,
    status: "coming_soon",
    recommendedFor: ["BGM 生成", "主题曲创作"],
  },
];

export const SCENE_TEMPLATES: GameSceneConfig[] = [
  {
    id: "npc-simple",
    name: "简单 NPC 对话",
    category: "npc",
    modelId: "gpt-4o",
    systemPrompt: "你是一个游戏 NPC。根据用户输入，生成符合角色设定的自然对话回复。回复应简洁，200字以内。",
    temperature: 0.8,
    maxTokens: 200,
    tools: ["knowledge_retrieval", "dialogue_history"],
    testInput: "玩家：你好，请问这里最近的城镇在哪里？",
  },
  {
    id: "quest-generator",
    name: "动态任务生成",
    category: "quest",
    modelId: "o1",
    systemPrompt: "你是任务设计助手。根据玩家当前状态和游戏世界观，生成一个有趣且合理的任务。",
    temperature: 0.7,
    maxTokens: 300,
    tools: [],
    testInput: "玩家等级：15，世界观：中世纪奇幻，当前地点：酒馆",
  },
  {
    id: "world-lore",
    name: "世界观 Lore 生成",
    category: "worldbuilding",
    modelId: "claude-3.5-sonnet",
    systemPrompt: "你是游戏世界观专家。根据已有设定，生成连贯的世界观内容，包括历史、地理、文化等。",
    temperature: 0.9,
    maxTokens: 500,
    tools: ["world_knowledge_base"],
    testInput: "现有设定：魔法石是这个世界的主要能源，已经使用了1000年",
  },
];

export function generateUnitySnippet(config: GameSceneConfig, model: GameModel): string {
  return `// Ludens-Flow 游戏内模型接入 - ${config.name}
  // 模型: ${model.name} (${model.provider})
  // 场景: ${config.category}

  using LudensFlow.Runtime;
  using UnityEngine;

  public class ${config.name.replace(/\s+/g, "")}Agent : MonoBehaviour
  {
      [SerializeField] private string apiKey = "YOUR_API_KEY";
      [SerializeField] private string endpoint = "${config.modelId === "custom" ? "YOUR_ENDPOINT" : "https://api.openai.com/v1/chat/completions"}";

      private LudensFlowAgent agent;

      void Start()
      {
          agent = new LudensFlowAgent(new AgentConfig
          {
              Model = "${model.id}",
              SystemPrompt = @"${config.systemPrompt}",
              Temperature = ${config.temperature}f,
              MaxTokens = ${config.maxTokens},
              Tools = new[] { ${config.tools.map(t => `"${t}"`).join(", ")} }
          });
      }

      public async void SendMessage(string playerInput)
      {
          var response = await agent.Chat(playerInput);
          Debug.Log($"[${config.name}] {response}");
      }
  }`;
}

export function generateRestApiSnippet(config: GameSceneConfig, model: GameModel): string {
  return `# Ludens-Flow Runtime API 接入配置
  # 场景: ${config.name}
  # 模型: ${model.name} (${model.provider})

SCENE_ID: ${config.id}
MODEL: ${model.id}
ENDPOINT: ${config.modelId === "custom" ? "YOUR_ENDPOINT" : "https://api.openai.com/v1/chat/completions"}

# 请求示例
curl -X POST \${ENDPOINT} \\
  -H "Authorization: Bearer \${API_KEY}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "${model.id}",
    "messages": [
      {"role": "system", "content": "${config.systemPrompt}"},
      {"role": "user", "content": "${config.testInput}"}
    ],
    "temperature": ${config.temperature},
    "max_tokens": ${config.maxTokens}
  }'`;
}