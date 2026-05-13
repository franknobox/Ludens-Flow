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
    id: "gpt-4.5",
    name: "GPT-4.5",
    provider: "OpenAI",
    description: "当前最新旗舰级模型，具备顶级的推理、代码和多模态能力，适合高难度剧情、任务生成和复杂指令的 NPC。",
    categories: ["npc", "quest", "narrative"],
    contextWindow: 128000,
    strengths: ["顶级推理", "深度逻辑", "长文连贯"],
    inputCostPer1M: 75,
    outputCostPer1M: 150,
    status: "recommended",
    recommendedFor: ["高难度 NPC 多轮对话", "核心剧情树构建", "动态任务生成"],
  },
  {
    id: "gpt-4o-mini",
    name: "GPT-4o Mini",
    provider: "OpenAI",
    description: "轻量快速且极具性价比的模型，适合频繁调用的简单对话或状态判定场景。",
    categories: ["npc", "quest"],
    contextWindow: 128000,
    strengths: ["低成本", "低延迟", "快速判定"],
    inputCostPer1M: 0.15,
    outputCostPer1M: 0.6,
    status: "popular",
    recommendedFor: ["简单 NPC 回复", "快速生成任务描述", "游戏状态分类"],
  },
  {
    id: "claude-3.7-sonnet",
    name: "Claude 3.7 Sonnet",
    provider: "Anthropic",
    description: "目前在代码和创意写作上表现最佳的模型，支持超长上下文，并具备内置的高级推理思考模式。",
    categories: ["narrative", "worldbuilding", "npc"],
    contextWindow: 200000,
    strengths: ["混合推理", "文笔极佳", "代码能力"],
    inputCostPer1M: 3,
    outputCostPer1M: 15,
    status: "recommended",
    recommendedFor: ["分支剧情生成", "世界观设定补全", "高质量文案写作"],
  },
  {
    id: "o3-mini",
    name: "o3-mini",
    provider: "OpenAI",
    description: "以极其快速的内部思考链解决复杂逻辑问题，且性价比极高，适合用于解谜设计与系统逻辑分析。",
    categories: ["quest", "worldbuilding"],
    contextWindow: 200000,
    strengths: ["快速推理", "解谜设计", "性价比高"],
    inputCostPer1M: 1.1,
    outputCostPer1M: 4.4,
    status: "popular",
    recommendedFor: ["关卡逻辑设计", "任务先决条件分析", "谜题解答验证"],
  },
  {
    id: "gemini-2.5-pro",
    name: "Gemini 2.5 Pro",
    provider: "Google",
    description: "拥有原生多模态能力与极长上下文窗口，适合读取整本游戏设计文档或几百张图片进行世界观推演。",
    categories: ["worldbuilding", "narrative", "image"],
    contextWindow: 2000000,
    strengths: ["2M 超长上下文", "原生多模态", "海量资料阅读"],
    inputCostPer1M: 1.25,
    outputCostPer1M: 5.0,
    status: "recommended",
    recommendedFor: ["整本 GDD 总结", "大规模世界观推演", "多章节剧情连贯性检查"],
  },
  {
    id: "gemini-2.5-flash",
    name: "Gemini 2.5 Flash",
    provider: "Google",
    description: "超快响应的多模态轻量级模型，能够实时处理音频或视觉输入，是构建实时反应型 NPC 的理想选择。",
    categories: ["npc", "voice"],
    contextWindow: 1000000,
    strengths: ["极致速度", "实时多模态反馈", "免费额度大"],
    inputCostPer1M: 0.075,
    outputCostPer1M: 0.3,
    status: "popular",
    recommendedFor: ["实时语音交互 NPC", "极速事件反馈流", "大量杂项文本生成"],
  },
  {
    id: "deepseek-r1",
    name: "DeepSeek-R1",
    provider: "DeepSeek",
    description: "国产顶级开源推理模型，逻辑能力可比肩全球顶尖闭源模型，价格极其亲民。",
    categories: ["quest", "narrative", "worldbuilding"],
    contextWindow: 128000,
    strengths: ["顶级开源", "极致性价比", "强逻辑推理"],
    inputCostPer1M: 0.55,
    outputCostPer1M: 2.19,
    status: "recommended",
    recommendedFor: ["低成本海量剧情生成", "复杂数值平衡推演", "开源私有化部署测试"],
  },
  {
    id: "deepseek-v3",
    name: "DeepSeek-V3",
    provider: "DeepSeek",
    description: "通用型主力模型，各方面能力均衡且具有极强的响应速度与成本优势。",
    categories: ["npc", "quest", "narrative"],
    contextWindow: 128000,
    strengths: ["通用强悍", "高速响应", "极低成本"],
    inputCostPer1M: 0.14,
    outputCostPer1M: 0.28,
    status: "popular",
    recommendedFor: ["日常 NPC 闲聊", "通用任务配置生成", "常规文案润色"],
  },
  {
    id: "dall-e-3",
    name: "DALL-E 3",
    provider: "OpenAI",
    description: "高质量且能严格遵循提示词的图像生成模型，适合生成游戏内的道具图标与概念草图。",
    categories: ["image"],
    contextWindow: 0,
    strengths: ["精确理解提示词", "风格一致性"],
    inputCostPer1M: 0,
    outputCostPer1M: 0,
    status: "recommended",
    recommendedFor: ["道具图标", "场景概念图", "角色设计参考"],
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
    modelId: "gpt-4.5",
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
    modelId: "o3-mini",
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
    modelId: "claude-3.7-sonnet",
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