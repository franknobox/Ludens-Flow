export type ModelCategory = "npc" | "world_narrative" | "quest_behavior" | "multimodal" | "world_model" | "image" | "video" | "audio";

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
  category: ModelCategory;
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
  { id: "npc", label: "NPC 对话", icon: "💬", hint: "角色对话、闲聊交互" },
  { id: "world_narrative", label: "世界观与剧情", icon: "📖", hint: "背景设定、多线剧情、台词" },
  { id: "quest_behavior", label: "任务与行为树", icon: "🧠", hint: "任务生成、决策树、行为推演" },
  { id: "multimodal", label: "多模态理解", icon: "👁️", hint: "图像解析、界面识别、音视频理解" },
  { id: "world_model", label: "世界模型仿真", icon: "🌍", hint: "物理规律、环境状态、复杂推演" },
  { id: "image", label: "图像生成", icon: "🎨", hint: "角色立绘、UI、概念图" },
  { id: "video", label: "视频生成", icon: "🎬", hint: "过场动画、动效生成" },
  { id: "audio", label: "声音与音乐", icon: "🎵", hint: "TTS、环境音、BGM" },
];

export const MOCK_MODELS: GameModel[] = [
  // --- NPC ---
  {
    id: "gpt-5.4-mini",
    name: "GPT-5.4 Mini",
    provider: "OpenAI",
    description: "高性价比且极速的轻量级模型，适合高频调用的日常 NPC 闲聊。",
    categories: ["npc", "quest_behavior"],
    contextWindow: 128000,
    strengths: ["低延迟", "极低成本", "基础对话"],
    inputCostPer1M: 0.75,
    outputCostPer1M: 4.5,
    status: "popular",
    recommendedFor: ["日常 NPC 闲聊", "简单状态分类"],
  },
  {
    id: "deepseek-v4-flash",
    name: "DeepSeek V4-Flash",
    provider: "DeepSeek",
    description: "国产通用高速大模型，成本极低，适合海量 NPC 并发响应。",
    categories: ["npc", "world_narrative"],
    contextWindow: 1000000,
    strengths: ["极致性价比", "长上下文", "通用响应"],
    inputCostPer1M: 0.14,
    outputCostPer1M: 0.28,
    status: "recommended",
    recommendedFor: ["大世界 NPC 动态生成", "基础剧情文案生成"],
  },
  {
    id: "gemma-4-26b",
    name: "Gemma 4 (26B)",
    provider: "Google (Open Weights)",
    description: "适合本地设备运行的强力开源 MoE 模型，可在本地 GPU 上提供高质量的低延迟 NPC 对话。",
    categories: ["npc"],
    contextWindow: 128000,
    strengths: ["本地部署", "无 API 成本", "隐私保护"],
    inputCostPer1M: 0,
    outputCostPer1M: 0,
    status: "popular",
    recommendedFor: ["单机游戏内置 AI", "低延迟离线对话"],
  },

  // --- 世界观与剧情 (World Narrative) ---
  {
    id: "claude-sonnet-4.6",
    name: "Claude Sonnet 4.6",
    provider: "Anthropic",
    description: "均衡旗舰模型，拥有顶尖的文笔和世界观逻辑一致性，是游戏剧情和台词撰写的最佳选择。",
    categories: ["world_narrative", "npc"],
    contextWindow: 200000,
    strengths: ["神级文笔", "人设一致性", "深度叙事"],
    inputCostPer1M: 3.0,
    outputCostPer1M: 15.0,
    status: "recommended",
    recommendedFor: ["核心 NPC 剧情线", "世界观设定补全", "高质量台词"],
  },
  {
    id: "qwen-3.5-32b",
    name: "Qwen 3.5 32B",
    provider: "Alibaba Cloud",
    description: "出色的开源多语言大模型，特别适合中文修仙、武侠等具有本土文化特色的剧情与世界观生成。",
    categories: ["world_narrative", "npc"],
    contextWindow: 128000,
    strengths: ["中文语境极佳", "开源免费", "本地部署"],
    inputCostPer1M: 0,
    outputCostPer1M: 0,
    status: "popular",
    recommendedFor: ["国风游戏剧情", "大量文案润色"],
  },

  // --- 任务与行为树 (Quest & Behavior) ---
  {
    id: "o3-mini",
    name: "o3-mini",
    provider: "OpenAI",
    description: "以内置思考链解决复杂逻辑问题，适合用于设计任务逻辑、前提条件分析和行为树节点生成。",
    categories: ["quest_behavior", "world_model"],
    contextWindow: 200000,
    strengths: ["逻辑推理", "数值平衡", "低成本推理"],
    inputCostPer1M: 1.1,
    outputCostPer1M: 4.4,
    status: "recommended",
    recommendedFor: ["关卡任务逻辑", "行为树自动生成", "系统规则判定"],
  },
  {
    id: "deepseek-v4-pro",
    name: "DeepSeek V4-Pro",
    provider: "DeepSeek",
    description: "顶级国产推理模型，能通过深度逻辑链解决高难度的数值体系和复杂行为树设计。",
    categories: ["quest_behavior", "world_narrative"],
    contextWindow: 128000,
    strengths: ["深度思考", "复杂设计", "代码/逻辑双绝"],
    inputCostPer1M: 0.435,
    outputCostPer1M: 0.87,
    status: "popular",
    recommendedFor: ["复杂经济系统推演", "动态任务树构建"],
  },
  {
    id: "gpt-5.4",
    name: "GPT-5.4",
    provider: "OpenAI",
    description: "新一代均衡旗舰，擅长从自然语言直接提取和生成 JSON 格式的复杂行为树结构。",
    categories: ["quest_behavior", "world_narrative"],
    contextWindow: 128000,
    strengths: ["结构化输出", "多步规划", "高可靠性"],
    inputCostPer1M: 2.5,
    outputCostPer1M: 15.0,
    status: "popular",
    recommendedFor: ["自动化行为逻辑脚本", "复杂状态机生成"],
  },

  // --- 多模态理解 (Multimodal) ---
  {
    id: "gemini-3.1-pro",
    name: "Gemini 3.1 Pro",
    provider: "Google",
    description: "原生多模态融合的王者，能同时输入超长视频、音频和图片，极适合分析玩家游玩录像或美术资源。",
    categories: ["multimodal", "world_narrative"],
    contextWindow: 2000000,
    strengths: ["音视频原生理", "2M 上下文", "界面元素定位"],
    inputCostPer1M: 2.0,
    outputCostPer1M: 12.0,
    status: "recommended",
    recommendedFor: ["玩家录像分析", "界面原型图解析", "音频情感识别"],
  },
  {
    id: "claude-opus-4.7",
    name: "Claude Opus 4.7",
    provider: "Anthropic",
    description: "当前最强的视觉感知与推演模型，极其适合识别游戏原画中的细微元素和进行高难度的图文逻辑匹配。",
    categories: ["multimodal", "world_model"],
    contextWindow: 200000,
    strengths: ["极高分辨率感知", "复杂场景推理", "细致分析"],
    inputCostPer1M: 5.0,
    outputCostPer1M: 25.0,
    status: "popular",
    recommendedFor: ["复杂场景解读", "UI 布局结构还原"],
  },

  // --- 世界模型仿真 (World Model) ---
  {
    id: "o3",
    name: "o3",
    provider: "OpenAI",
    description: "目前顶级的推理大模型，被广泛用作游戏 Agent 的“决策引擎”，推演长线环境变化和复杂物理互动逻辑。",
    categories: ["world_model", "quest_behavior"],
    contextWindow: 200000,
    strengths: ["长线因果推演", "超强纠错", "环境状态机"],
    inputCostPer1M: 15.0,
    outputCostPer1M: 60.0,
    status: "recommended",
    recommendedFor: ["全服经济生态推演", "NPC 社会网络模拟"],
  },
  {
    id: "llama-4-scout",
    name: "Llama 4 Scout",
    provider: "Meta",
    description: "专为巨量上下文（10M）打造的 MoE 模型，能一次性读入整个游戏的物理规则与背景代码进行状态模拟。",
    categories: ["world_model", "npc"],
    contextWindow: 10000000,
    strengths: ["千万级上下文", "开源部署", "规则长期记忆"],
    inputCostPer1M: 0,
    outputCostPer1M: 0,
    status: "popular",
    recommendedFor: ["大世界持久化记忆", "规则引擎沙盒演练"],
  },

  // --- 图像生成 (Image) ---
  {
    id: "flux-2-pro",
    name: "Flux 2 Pro",
    provider: "Black Forest Labs",
    description: "目前在光影质感、文字渲染和相片写实度上首屈一指的模型，非常适合生成高品质游戏美术素材。",
    categories: ["image"],
    contextWindow: 0,
    strengths: ["顶级写实", "文字完美渲染", "精准控图"],
    inputCostPer1M: 0,
    outputCostPer1M: 0,
    status: "recommended",
    recommendedFor: ["UI 图标设计", "场景概念原画", "游戏海报"],
  },
  {
    id: "midjourney-v8.1",
    name: "Midjourney V8.1",
    provider: "Midjourney",
    description: "业内最强艺术表现力，支持 2K HD 与个性化风格训练，是游戏气氛图、角色设定的灵感利器。",
    categories: ["image"],
    contextWindow: 0,
    strengths: ["艺术感拉满", "2K 高清", "风格融合"],
    inputCostPer1M: 0,
    outputCostPer1M: 0,
    status: "popular",
    recommendedFor: ["角色立绘探索", "氛围场景构建"],
  },
  {
    id: "gpt-image-1.5",
    name: "GPT Image 1.5",
    provider: "OpenAI",
    description: "全面替代 DALL-E 3 的新一代图像模型，能完美结合复杂的上下文环境生成极度符合提示词的画面。",
    categories: ["image"],
    contextWindow: 0,
    strengths: ["极强提示词遵循", "多目标生成一致"],
    inputCostPer1M: 0,
    outputCostPer1M: 0,
    status: "popular",
    recommendedFor: ["剧情过场插图", "批量物品图鉴"],
  },

  // --- 视频生成 (Video) ---
  {
    id: "veo-3.1",
    name: "Veo 3.1",
    provider: "Google",
    description: "真 4K 影视级视频生成模型，并自带原生音效生成，是制作高质量游戏宣传片和过场动画的标杆。",
    categories: ["video"],
    contextWindow: 0,
    strengths: ["4K 分辨率", "原生带音效", "电影级画质"],
    inputCostPer1M: 0,
    outputCostPer1M: 0,
    status: "recommended",
    recommendedFor: ["游戏宣发视频", "核心过场动画生成"],
  },
  {
    id: "kling-3.0",
    name: "Kling 3.0",
    provider: "Kuaishou",
    description: "以超长的生成时长（可达120秒）和极具竞争力的价格著称，是批量化生成游戏内动态元素的利器。",
    categories: ["video"],
    contextWindow: 0,
    strengths: ["超长视频", "高性价比", "大动态表现"],
    inputCostPer1M: 0,
    outputCostPer1M: 0,
    status: "popular",
    recommendedFor: ["游戏场景循环动效", "角色待机动画预览"],
  },
  {
    id: "runway-gen-4.5",
    name: "Runway Gen-4.5",
    provider: "Runway",
    description: "提供极高自由度的精细控制（运动画笔、机位运镜），适合对镜头表现有极高要求的创作者。",
    categories: ["video"],
    contextWindow: 0,
    strengths: ["精准运镜控制", "专业级编辑", "角色一致性"],
    inputCostPer1M: 0,
    outputCostPer1M: 0,
    status: "popular",
    recommendedFor: ["镜头感强烈的 Cutscene", "动态特效参考"],
  },

  // --- 声音与配音 (Audio) ---
  {
    id: "eleven-v3",
    name: "Eleven v3",
    provider: "ElevenLabs",
    description: "当前业内最逼真的情感 TTS 模型，能通过 [叹气] [大喊] 等标签驱动极其丰富的角色语音。",
    categories: ["audio"],
    contextWindow: 0,
    strengths: ["情感标签驱动", "极致拟真", "瞬时声音克隆"],
    inputCostPer1M: 0,
    outputCostPer1M: 0,
    status: "recommended",
    recommendedFor: ["主角全量配音", "剧情沉浸式旁白"],
  },
  {
    id: "suno-v5.5",
    name: "Suno v5.5",
    provider: "Suno",
    description: "强大的音乐生成模型，支持极高质量的人声和旋律生成，还能模仿特定的参考风格进行作曲。",
    categories: ["audio"],
    contextWindow: 0,
    strengths: ["极佳人声", "风格模仿", "易用性极高"],
    inputCostPer1M: 0,
    outputCostPer1M: 0,
    status: "popular",
    recommendedFor: ["游戏主题曲创作", "酒馆/村落环境 BGM"],
  },
  {
    id: "udio-v4",
    name: "Udio v4",
    provider: "Udio",
    description: "主打 48kHz 高保真和专业级音乐控制，支持乐器分离和局部音轨修复，深受独立游戏开发者喜爱。",
    categories: ["audio"],
    contextWindow: 0,
    strengths: ["48kHz 高保真", "分轨导出", "局部重绘(Inpainting)"],
    inputCostPer1M: 0,
    outputCostPer1M: 0,
    status: "recommended",
    recommendedFor: ["战斗/Boss 高燃 BGM", "专业音轨混音素材"],
  },
];

export const SCENE_TEMPLATES: GameSceneConfig[] = [
  {
    id: "npc-simple",
    name: "酒馆老板对话",
    category: "npc",
    modelId: "gpt-5.4-mini",
    systemPrompt: "你是一个热情的中世纪酒馆老板。玩家来打听情报。回复尽量简短（50字内），要有口音和场景互动（如擦桌子）。",
    temperature: 0.8,
    maxTokens: 150,
    tools: ["knowledge_retrieval", "dialogue_history"],
    testInput: "玩家：老板，最近城外有什么奇怪的动静吗？",
  },
  {
    id: "quest-generator",
    name: "动态悬赏任务生成",
    category: "quest_behavior",
    modelId: "o3-mini",
    systemPrompt: "你是任务生成引擎。根据当前大地图状态和玩家等级，生成一个符合逻辑的悬赏任务，输出 JSON 包含：任务名、目标、行为树节点数组、奖励。",
    temperature: 0.3,
    maxTokens: 500,
    tools: ["map_state_query"],
    testInput: "玩家等级：20，当前位置：黑木林，近期事件：兽人部落集结。",
  },
  {
    id: "world-lore",
    name: "世界观纪元史料生成",
    category: "world_narrative",
    modelId: "claude-sonnet-4.6",
    systemPrompt: "你是首席世界观架构师。根据已有的关键词和设定残篇，用史诗般宏大的文笔补全该纪元的历史传说，确保前后逻辑不穿帮。",
    temperature: 0.9,
    maxTokens: 1000,
    tools: ["lore_database"],
    testInput: "关键词：星辰坠落、失落的魔法文明、水晶腐化。要求写一段流传在吟游诗人间的传说。",
  },
  {
    id: "vision-analyzer",
    name: "玩家 UI 布局解析",
    category: "multimodal",
    modelId: "gemini-3.1-pro",
    systemPrompt: "你是 UX 专家。解析玩家上传的游戏截图，指出界面布局的可用性问题，并给出改进建议。",
    temperature: 0.5,
    maxTokens: 500,
    tools: [],
    testInput: "[上传图片] 这里是我们的战斗界面，玩家反馈经常找不到血瓶。你怎么看？",
  },
  {
    id: "world-simulation",
    name: "全服经济生态推演",
    category: "world_model",
    modelId: "o3",
    systemPrompt: "你是游戏经济系统仿真 Agent。我将输入一周内的资源产出销毁日志，请推演未来 30 天内金币的通胀率，并建议调节策略。",
    temperature: 0.2,
    maxTokens: 800,
    tools: ["economy_logs_query", "math_simulator"],
    testInput: "本周金币总产出：1.5亿，总销毁：0.8亿，活跃玩家：5万。商行物价指数上涨 12%。",
  }
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