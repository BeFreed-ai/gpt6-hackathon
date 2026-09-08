# LLM 小人社会模拟器：系统设计与开发计划

## 1. 项目目标

构建一个可观察、可回放的 2D 多智能体社会实验：每个黄色小人都由独立的 LLM Agent 驱动，只能依据自己的身体状态、亲身经历、局部观察、他人转述和媒体广播做决定。

项目不预设“领袖”“记者”“宗教”“政府”等社会结构。系统只提供生存条件、环境规则、通信媒介和基础动作，观察合作、分工、权力、谣言、规范与冲突是否从个体行为中自然产生。

### 1.1 核心原则

1. 世界服务器拥有唯一的客观事实。
2. 每个 Agent 只拥有自己的主观认知。
3. LLM 决定目标、语言和高级行为；程序负责身体、物理和规则验证。
4. Agent 可以共用同一个模型，但身份、历史、记忆和调用上下文必须独立。
5. 社会现象从基础动作中产生，不提供 `become_leader`、`create_religion` 等捷径。
6. 默认地图只展示公开行为。点击小人后，才显示其目标、价值观、关系和个人历史。
7. 完整实验必须能够保存、回放和对照分析。

### 1.2 第一版不做

- 3D 场景和复杂动画。
- 数百或数千个实时 Agent。
- 联机多人模式。
- 语音识别或语音合成。
- 复杂战斗、遗传和经济系统。
- 系统替 Agent 编写固定世界观或职业。

## 2. 推荐技术栈

第一版不依赖游戏引擎，直接运行在浏览器中。

| 层 | 推荐技术 | 作用 |
| --- | --- | --- |
| 2D 前端 | TypeScript + PixiJS 或 Phaser | 地图、小人、建筑、动画和点击交互 |
| UI | React | Agent 面板、事件日志、控制台和实验视图 |
| 服务端 | Python + FastAPI | 世界模拟、Agent 调度、WebSocket API |
| 数据校验 | Pydantic | 事件和 LLM 动作的结构化验证 |
| 并发 | asyncio | 并行执行多个独立 LLM 请求 |
| 数据库 | SQLite | 世界事件、Agent 记忆、实验和调用记录 |
| 实时同步 | WebSocket | 将世界快照和增量事件推送给浏览器 |
| LLM | Provider Adapter | 隔离具体模型供应商，便于替换模型和做对照实验 |

## 3. 总体架构

```text
浏览器 2D 客户端
  ├── 世界渲染
  ├── Agent 详情面板
  ├── 事件与广播面板
  └── 玩家干预工具
             ↕ WebSocket / HTTP
Python 世界服务器
  ├── World Simulation
  ├── Event Store
  ├── Perception Resolver
  ├── Communication System
  ├── Agent Runtime + Scheduler
  ├── Memory Retrieval
  ├── LLM Gateway
  ├── Action Validator + Executor
  └── Experiment Recorder
             ↕
          SQLite
```

一轮完整的数据流：

```text
世界发生事件
→ 感知系统计算哪些 Agent 能知道
→ 为每个 Agent 生成不同的私人认知事件
→ 事件进入各自邮箱
→ 调度器决定是否唤醒 Agent
→ Agent 使用自己的上下文调用 LLM
→ LLM 提交结构化动作意图
→ 世界验证并按 tick 结算动作
→ 产生新的世界事件
```

## 4. 核心数据模型

### 4.1 世界事件 WorldEvent

世界事件描述客观发生的事情，仅服务器和研究者模式可以看到完整内容。

```json
{
  "event_id": "evt_1038",
  "experiment_id": "exp_001",
  "world_time": 128.4,
  "type": "agent_attacked",
  "actor_id": "yellow_04",
  "target_ids": ["yellow_09"],
  "position": [14, 8],
  "payload": {"damage": 3},
  "caused_by": "evt_1032"
}
```

### 4.2 私人认知 PerceivedEvent

同一个世界事件会为不同 Agent 生成不同认知。

```json
{
  "memory_id": "mem_701",
  "agent_id": "yellow_07",
  "world_time": 128.4,
  "content": "I saw Yellow 04 attack Yellow 09.",
  "source_type": "direct_observation",
  "source_id": "yellow_04",
  "confidence": 1.0,
  "original_event_id": "evt_1038",
  "tags": ["violence", "yellow_04", "yellow_09"]
}
```

认知来源至少包括：

- `direct_experience`：亲身经历。
- `direct_observation`：亲眼看见。
- `overheard`：在附近听见。
- `testimony`：别人告诉它。
- `broadcast`：从广播接收。
- `document`：从文字或标记读取。
- `inference`：Agent 自己做出的推测。

转述和广播不能自动成为事实。例如数据库应记录“广播声称北方没有食物”，而不是“北方没有食物”。

### 4.3 AgentState

```json
{
  "agent_id": "yellow_07",
  "name": "Mimo",
  "position": [10, 4],
  "health": 9,
  "hunger": 0.3,
  "energy": 0.7,
  "inventory": ["apple_02"],
  "initial_traits": {
    "curiosity": 0.8,
    "empathy": 0.6,
    "risk_tolerance": 0.3
  },
  "active_goal": null,
  "current_action": null,
  "status": "idle"
}
```

初始性格只提供轻微倾向，不指定职业或社会角色。

### 4.4 Goal

目标由 Agent 自己生成，而不是从职业列表选择。

```json
{
  "goal_id": "goal_19",
  "agent_id": "yellow_07",
  "statement": "确认北方是否真的没有食物",
  "reason": "广播可能不可靠",
  "priority": 0.8,
  "commitment": 0.7,
  "success_condition": "亲自观察北方的食物状况",
  "created_from_memory_ids": ["mem_701", "mem_694"],
  "status": "active"
}
```

目标保留承诺度，避免 Agent 每次调用都完全改变方向。目标完成、失败、长期停滞或遇到重大事件时才进行重新反思。

## 5. 模块设计

### 5.1 World Simulation：世界模拟

职责：

- 管理地图、坐标、碰撞和世界时间。
- 管理 Agent、资源、物品、建筑和广播设备。
- 更新饥饿、体力、伤害、死亡和资源再生。
- 接收动作意图并在固定 tick 中统一结算。
- 生成客观 `WorldEvent`。

实现建议：

- 使用固定时间步，例如每秒 5 个 simulation tick。
- 所有世界变更只允许发生在该模块中。
- LLM 响应只产生“意图”，不能直接修改实体状态。
- 为每个实体维护版本号；迟到的 LLM 动作必须重新验证。
- 第一版使用方格地图和简单 A* 寻路。

关键接口：

```python
class WorldSimulation:
    def snapshot_for_renderer(self) -> dict: ...
    def submit_intent(self, intent: "ActionIntent") -> None: ...
    def tick(self, delta_seconds: float) -> list["WorldEvent"]: ...
```

### 5.2 Event System：事件系统

职责：

- 为每个客观事件分配唯一 ID 和世界时间。
- 保存因果关系，例如某次攻击源于哪一个动作。
- 把事件交给感知与通信系统。
- 将所有事件追加写入数据库，支持完整回放。

事件日志只追加、不原地修改。状态由事件重建或定期快照恢复。

### 5.3 Perception System：感知系统

职责：

- 计算 Agent 的视野、听觉范围和遮挡。
- 把客观事件转换为该 Agent 能理解的私人描述。
- 保留信息来源、置信度和原始事件引用。
- 将私人事件投递到 Agent 的邮箱与记忆库。

第一版规则：

- 视野使用圆形距离，墙体可以阻挡。
- 普通讲话只有近距离目标及旁听者能听见。
- 喊话半径更大，但不保证识别说话者。
- 远处打斗可以只产生“听见异常声响”的模糊信息。
- Agent 不会因为另一个 Agent 知道某事而自动知道该事。

关键接口：

```python
class PerceptionResolver:
    def resolve(
        self,
        event: "WorldEvent",
        world: "WorldState",
    ) -> list["PerceivedEvent"]: ...
```

### 5.4 Agent Runtime：独立 Agent 运行时

每个小人是一个逻辑 Actor，不是一个 OS 线程。

每个 Actor 拥有：

- 唯一身份和独立 LLM 上下文。
- 私人事件邮箱。
- 自己的记忆、目标、承诺与当前动作。
- 一个串行决策锁，防止同一个 Agent 同时思考两次。

生命周期：

```text
接收私人事件
→ 判断是否需要思考
→ 构造只属于自己的上下文
→ 调用 LLM
→ 验证返回结构
→ 提交动作意图
→ 接收世界执行结果
→ 写入个人历史
```

多个 Agent 的 LLM 请求可以通过 `asyncio` 并行执行，并用 semaphore 控制并发量。世界动作仍按 tick 集中结算，以保证一致性。

### 5.5 Scheduler：决策调度器

职责：决定哪个 Agent 什么时候调用 LLM。

唤醒条件：

- 当前高级动作完成或失败。
- 收到别人说话或新闻广播。
- 发现食物、危险、死亡等重要事件。
- 饥饿、体力或安全进入阈值。
- 当前目标长期没有进展。
- 到达低频的自我反思时间。

没有被唤醒的 Agent 继续执行走路、采集、休息等已有动作。不要按游戏帧调用 LLM。

建议第一版：

- 每个 Agent 最短思考间隔 10 秒。
- 普通反思间隔 30～90 秒，并加入随机抖动。
- 紧急事件允许提前唤醒。
- 同时在途的 LLM 请求限制为 4～8 个。

### 5.6 Memory System：个人记忆

保存两套互相隔离的历史：

1. `world_events`：完整客观历史，只供服务器、回放和研究者查看。
2. `agent_memories`：每个 Agent 真正经历、看见、听见或推测过的内容。

第一阶段可以把某个 Agent 的全部个人历史放入请求。随着历史增长，改成：

```text
最近个人历史
+ 当前相关人物的旧事件
+ 当前地点的旧事件
+ 与当前目标相关的旧事件
+ 未完成的承诺
```

完整原始历史永久保存在数据库中。系统不替 Agent 写固定世界观。

允许保存两种由 Agent 自己产生的长期内容：

- 明确表达过的信念，例如“我认为广播站被 Piko 控制”。
- 自我描述，例如“我想成为保护弱者的人”。

这些内容仍然需要保留来源和时间，并允许 Agent 在未来修改或否定。

### 5.7 LLM Gateway：模型调用层

职责：

- 为每个 Agent 构建独立输入。
- 调用模型并要求返回结构化结果。
- 处理超时、限流、失败和非法 JSON。
- 记录模型、延迟、token 使用量和请求 ID。
- 提供模型供应商适配层，便于切换和做对照实验。

每次输入只包含：

```text
身份与初始倾向
身体状态
当前局部观察
刚收到的私人事件
最近与相关的个人历史
当前目标和未完成承诺
合法动作及世界能力说明
```

建议返回结构：

```json
{
  "goal_update": {
    "operation": "keep",
    "goal": null
  },
  "public_reason": "我想亲自确认广播内容",
  "action": {
    "type": "move",
    "parameters": {"destination": [18, 6]}
  },
  "speech": null,
  "new_beliefs": [],
  "important_memory_ids": ["mem_701"]
}
```

`public_reason` 是用于 UI 的简短自述，不保存或展示模型隐藏推理过程。

### 5.8 Action System：动作定义、验证与执行

第一版动作集合：

| 动作 | 主要验证 |
| --- | --- |
| `move` | 目的地可达、移动距离合法 |
| `look` | 观察方向和范围合法 |
| `take` | 物品存在、距离足够、背包有空间 |
| `drop` | Agent 确实持有物品 |
| `eat` | 食物存在且可食用 |
| `give` | 双方距离足够且给予者持有物品 |
| `gather` | 资源存在、距离和工具满足要求 |
| `build` | 地块、资源和建造时间满足要求 |
| `rest` | 地点允许休息 |
| `talk` | 目标在交流距离内 |
| `whisper` | 目标非常靠近 |
| `shout` | 消耗体力并向一定范围传播 |
| `broadcast` | 位于可用广播站且设备有能源 |
| `write` | 持有材料并位于可写对象附近 |
| `read` | 文字可见且 Agent 具备读取条件 |
| `attack` | 目标在攻击范围内 |
| `help` | 目标需要帮助且距离足够 |
| `wait` | 始终合法 |

不要提供社会结果动作，例如 `form_government`。Agent 可以通过讲话、承诺、给予、拒绝、占有和合作，使组织从实际行为中形成。

每个动作返回明确结果：`accepted`、`completed`、`failed` 或 `interrupted`。失败原因也作为 Agent 的私人经历返回。

### 5.9 Communication System：交流与新闻广播

支持四种传播方式：

1. `talk`：指定目标，附近小人可能旁听。
2. `whisper`：传播范围很小。
3. `shout`：覆盖范围较大，消耗更多体力。
4. `broadcast`：通过世界中的广播设备传播。

广播站是一个真实世界实体：

```json
{
  "station_id": "radio_01",
  "position": [30, 12],
  "channel": "NEWS_ONE",
  "power": 50,
  "coverage_radius": 80,
  "energy": 0.75,
  "requires_operator": true
}
```

广播流程：

```text
Agent 到达广播站
→ 提交 broadcast(message)
→ 验证使用权、能源和设备状态
→ 产生 RadioTransmission
→ 根据功率、距离、频道和接收器计算听众
→ 为每位听众生成私人 broadcast 记忆
```

接收者记住的是“某广播源声称 X”，不是直接相信 X。广播可能是真相、错误信息或有意宣传。

### 5.10 Player Intervention：玩家干预

第一版提供：

- 投放食物或资源。
- 放置、移动或移除障碍。
- 制造雷击或局部天气。
- 建造一个中立广播设备。
- 直接与指定 Agent 说话。

玩家操作也必须生成普通 `WorldEvent`，通过同一感知系统传播。Agent 不应因为事件来自玩家就自动获得额外信息。

### 5.11 Storage & Replay：存储与回放

至少保存：

- 实验配置和随机种子。
- 所有世界事件。
- 所有私人认知事件。
- Agent 状态快照。
- LLM 输入、结构化输出、延迟和 token 统计。
- 玩家干预。

建议每隔固定世界时间保存快照，回放时加载最近快照，再重放后续事件。相同种子和相同已记录 LLM 输出必须能够确定性复现一局实验。

### 5.12 Observer UI：观察界面

默认地图只显示：

- 位置、动作和动画。
- 公开说出口的话。
- 可被玩家听见的广播。
- 世界中的资源和建筑。

不在每个小人头顶持续展示价值观或内心目标。

点击一个小人后打开详情面板：

```text
名字与身体状态
正在做什么
当前目标
它自己表达过的价值观
系统观察到的长期行为倾向
信任与敌对关系
它的个人历史
信息来源和置信度
当前公开理由
```

“自我表达的价值观”和“行为统计”应分开。例如它可以认为自己重视公平，但长期行为显示它经常囤积资源。

界面包含两种模式：

- 玩家模式：只显示公开信息和正常游戏交互。
- 研究者模式：可以查看 Agent 的私人记忆、目标、LLM 请求以及客观世界日志。

点击查看默认不会生成世界事件，也不会被 Agent 察觉。主动说话、触碰或干预使用单独操作。

## 6. API 与实时同步

建议的服务端接口：

```text
POST /experiments                 创建实验
POST /experiments/{id}/start      开始
POST /experiments/{id}/pause      暂停
POST /experiments/{id}/step       单步执行
POST /experiments/{id}/intervene  玩家干预
GET  /experiments/{id}/agents     Agent 列表
GET  /agents/{id}                 Agent 详情
GET  /agents/{id}/memories        私人历史
GET  /experiments/{id}/events     客观事件
WS   /experiments/{id}/stream     世界增量和公开事件
```

前端不应直接访问 LLM API 密钥。所有模型调用都从 Python 服务端发起。

## 7. 并发与一致性

- Agent 的独立 LLM 调用没有顺序依赖，应并行执行。
- 同一个 Agent 的思考请求必须串行，避免目标相互覆盖。
- 所有动作先进入意图队列，再由世界 tick 统一结算。
- 同一资源被多个 Agent 争夺时，使用稳定且可记录的结算规则。
- LLM 返回时重新验证动作，处理世界已经变化的情况。
- 超时不阻塞世界；Agent 保持当前动作或进入 `wait`。

## 8. 可观测性与研究指标

每局实验至少统计：

- Agent 存活时间和死亡原因。
- 对话与广播传播路径。
- 资源给予、交换、囤积和抢夺。
- 合作建造次数。
- 冲突、帮助和互惠次数。
- 每个 Agent 的关系网络。
- 某条信息传播到多少人、传播中发生多少变化。
- LLM 请求数、延迟、失败率和 token 用量。

后续可以计算：

- 社交网络中心性，观察是否出现事实领袖。
- 资源分配不平等程度。
- 群体或派系的稳定性。
- 谣言与事实的偏差。
- 危机前后合作水平变化。

## 9. 测试策略

### 单元测试

- 感知范围和遮挡是否正确。
- 广播覆盖、频道和能源是否正确。
- Agent 之间是否发生信息泄漏。
- 动作验证是否阻止非法世界修改。
- 同一物品争夺是否只有一个成功者。
- 事件回放能否重建相同状态。

### 集成测试

- 一个 Agent 能观察、思考、行动并收到结果。
- 两个 Agent 可以交谈且远处 Agent 不会知道内容。
- 广播只到达覆盖范围内且打开接收器的 Agent。
- 多个 LLM 请求并发时世界仍保持一致。
- 暂停、单步和恢复不会丢失事件。

### 实验对照

- 正常组：有长期记忆并允许交流。
- 无记忆组：只看当前环境。
- 无通信组：不能说话或广播。
- 广播组：加入由某个 Agent 控制的媒体。

不要在提示词中要求 Agent 建立社会、选举领袖或创造宗教。测试的是这些结构是否自然出现。

## 10. MVP 开发阶段

### 阶段一：确定性世界

- 显示 2D 地图、8 个小人、苹果和墙体。
- 实现移动、观察、拿取、吃、给予和等待。
- 完成世界事件日志和回放。
- 先用简单脚本 Agent 验证物理与数据流。

验收：不用 LLM 也能稳定运行 30 分钟，并准确回放。

### 阶段二：单个 LLM Agent

- 接入 LLM Gateway。
- 实现结构化动作输出。
- 完成独立历史、目标和失败反馈。
- 增加点击 Agent 的详情面板。

验收：Agent 能根据自己的观察产生目标，并用合法动作推进目标。

### 阶段三：8 个独立 Agent

- 为每个小人建立独立 Actor、邮箱和历史。
- 并行执行独立 LLM 请求。
- 实现面对面说话、旁听和喊话。
- 检查不存在全局信息泄漏。

验收：一个 Agent 获得的信息不会自动出现在其他 Agent 的上下文中。

### 阶段四：广播与玩家干预

- 添加广播站、接收器、频道、能源和覆盖范围。
- 添加食物投放、墙体和雷击。
- 实现信息来源与置信度展示。

验收：广播内容只影响实际接收到信号的 Agent，而且接收者知道消息来源而非把它当作客观事实。

### 阶段五：社会实验面板

- 添加关系图、传播链、资源统计和调用成本。
- 支持实验配置、随机种子、保存和完整回放。
- 运行正常、无记忆、无通信三组对照实验。

验收：可以用日志证据回答“某个群体行为是如何产生的”。

## 11. MVP 成功标准

第一版不是以“社会一定形成”为成功条件。成功条件是实验机制可信：

1. 8 个 Agent 能连续运行至少 30 分钟。
2. 每个 Agent 只能访问自己的认知历史。
3. Agent 能自由产生并坚持一段时间的目标。
4. 信息只能通过观察、交谈、文字或广播传播。
5. 玩家干预会通过正常感知链影响 Agent。
6. 所有行为能够追溯到观察、记忆、目标和动作结果。
7. 实验可以保存、回放并重复比较。

只要这些条件成立，即使第一局没有形成稳定社会，也仍然得到了一次有效实验；之后可以通过调整环境压力、通信条件和运行时间继续观察。

## 12. 推荐目录结构

```text
backend/
├── app/main.py
├── world/
│   ├── simulation.py
│   ├── state.py
│   ├── entities.py
│   └── clock.py
├── events/
│   ├── schemas.py
│   └── store.py
├── perception/
│   ├── vision.py
│   ├── hearing.py
│   └── resolver.py
├── agents/
│   ├── runtime.py
│   ├── scheduler.py
│   ├── memory.py
│   └── prompt_builder.py
├── actions/
│   ├── schemas.py
│   ├── validator.py
│   └── executor.py
├── communication/
│   ├── speech.py
│   └── radio.py
├── llm/
│   ├── base.py
│   └── client.py
├── storage/
│   ├── database.py
│   └── replay.py
└── api/
    ├── routes.py
    └── websocket.py

frontend/
├── src/world/
├── src/agents/
├── src/events/
├── src/experiments/
└── src/player-controls/

tests/
├── unit/
├── integration/
└── fixtures/
```

最先实现的纵向切片应是：一个 Agent 看见一个苹果，自主决定拿取并吃掉，世界验证动作，个人记忆记录结果，浏览器可以点击它查看全过程。该链路打通后，再扩展到多 Agent、对话和广播。
