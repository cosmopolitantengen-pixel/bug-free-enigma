# PROJECT_IDEA_FOR_CODEX.md

# AI Company OS / AI 公司操作系统完整需求说明

## 0. 给 Codex 的第一句话

你现在要帮我开发的不是普通聊天机器人，不是一个简单 AI 助手，也不是某个平台、某个行业的小工具。

我要做的是一个通用的 **AI Company OS / AI 公司操作系统**。

它的目标是：

把一个完整公司里的大脑、岗位、部门、技能、工具、工作流、记忆、知识库、权限、审批、风控、审计、评测、复盘、自我进化，全部做成一个可运行、可扩展、可控制的 AI 系统。

用户是最高 Root 老板。

AI 是公司大脑和 AI 员工团队。

AI 可以思考、拆任务、分配任务、调用 Skill、调用工具、互相对话、开会、质检、复盘、升级自己。

但所有高风险动作必须经过人工确认，部分危险动作必须默认禁止。

第一版先做给我自己用，不要一上来就绑定某个平台、某个行业，也不要先做复杂商业定价系统。第一阶段先把底层系统打牢。

---

# 1. 项目名称

英文名：

```text
AI Company OS
```

中文名：

```text
AI 公司操作系统 / AI 公司大脑
```

核心一句话：

```text
把完整公司的岗位做成 Agent，把岗位能力做成 Skill，把公司流程做成 Workflow，把工具统一接入，把经验写入 Memory，把规则写入 Knowledge Base，把危险动作交给 Permission 和 Approval，把所有行为写入 Audit Log，最后通过 Dashboard 给 Human Root 控制。
```

---

# 2. 项目不是做什么

这个项目不是：

```text
不是普通聊天机器人
不是单个 AI 助手
不是单个平台自动化工具
不是单个行业工具
不是没有权限控制的全自动系统
不是黑产工具
不是盗号工具
不是钓鱼工具
不是刷量工具
不是绕过验证码工具
不是攻击系统工具
不是保证赚钱系统
```

这个项目也不是一开始就固定在某个业务里。

不要默认写死某个平台、某个行业、某个具体生意。

平台、行业、业务，后面都应该作为插件、模板、Workflow 或 Adapter 接入。

---

# 3. 项目到底是什么

它是一个通用 AI 公司操作系统。

完整结构是：

```text
AI 董事会
+ AI CEO
+ AI 部门负责人
+ AI 员工 Agent
+ Skill 技能库
+ Workflow 流程引擎
+ Tool 工具层
+ Memory 记忆系统
+ Knowledge Base 知识库
+ Permission 权限系统
+ Approval 审批中心
+ Risk 风控系统
+ Audit 审计日志
+ Evaluation 评测系统
+ Dashboard 控制台
+ Agent Factory
+ Skill Factory
+ GitHub 吸收进化模块
+ Human Root 最高控制权
```

大白话：

```text
用户给目标。
AI CEO 理解目标。
项目经理 Agent 拆任务。
不同 Agent 分工。
Agent 调用 Skill 干活。
Skill 不够就申请补 Skill。
Agent 不够就申请补 Agent。
Workflow 把完整流程串起来。
工具层连接文件、数据库、API、GitHub、电脑等。
权限系统判断能不能执行。
风控系统检查风险。
需要人工确认的进入审批中心。
所有行为写审计日志。
完成后写入记忆和知识库。
复盘系统总结经验。
系统越用越完整。
```

---

# 4. 最高原则

## 4.1 Human Root 永远最高

权限顺序：

```text
Human Root > AI 董事会 > AI CEO > 部门负责人 Agent > 普通 Agent > Skill > Tool
```

AI 不能绕过用户。

AI 不能自己升级到 Root。

AI 不能关闭风控。

AI 不能删除审计日志。

AI 不能自己决定高风险动作。

---

## 4.2 安全优先级

所有决策优先级：

```text
安全 > 合规 > 数据隐私 > 账号健康 > 用户确认 > 质量 > 成本 > 效率 > 增长
```

不要为了效率破坏安全。

不要为了完成任务绕过审批。

不要为了增长做虚假承诺。

---

## 4.3 第一版先做底层，不绑定具体业务

第一版重点是做：

```text
用户系统
Agent 注册系统
Skill 注册系统
Workflow 引擎
任务系统
权限系统
审批系统
风控系统
审计日志
记忆系统
知识库系统
基础控制台
基础测试
可运行部署
```

第一版暂时不要重点做：

```text
复杂商业定价
完整 CRM 商业系统
复杂外部平台发布
真实资金自动操作
高度危险电脑控制
大规模自动群发
```

这些以后可以扩展，但第一版必须先把安全、权限、审计、Agent、Skill、Workflow 打牢。

---

# 5. 系统简单分类

整个系统可以用 8 个字分类：

```text
脑、人、技、流、器、记、控、看
```

含义：

```text
脑 = AI 大脑、AI CEO、AI 董事会
人 = 各种 Agent 员工
技 = Skill 技能
流 = Workflow 流程
器 = 工具、API、软件、电脑
记 = 记忆、知识库
控 = 权限、安全、审批、风控
看 = 控制台、日志、评测、报表
```

也可以简单理解成：

```text
AI 大脑
AI 员工
技能库
流程引擎
工具系统
记忆知识库
权限风控
控制台
```

---

# 6. 系统总架构

```text
AI Company OS
│
├── 1. Company Core 公司核心
│   ├── 公司宪法
│   ├── 经营目标
│   ├── 权限规则
│   ├── 风控红线
│   ├── 人工 Root 最高权限
│   └── 审计留痕
│
├── 2. Agent Organization Agent 组织层
│   ├── AI 董事会
│   ├── AI CEO
│   ├── 部门负责人 Agent
│   ├── 员工 Agent
│   ├── 反对 Agent
│   ├── 审查 Agent
│   ├── 仲裁 Agent
│   └── Agent Factory
│
├── 3. Skill Market 技能市场
│   ├── 文档 Skill
│   ├── 内容 Skill
│   ├── 图片 Skill
│   ├── 视频 Skill
│   ├── 数据 Skill
│   ├── 销售 Skill
│   ├── 客服 Skill
│   ├── 法务 Skill
│   ├── 财务 Skill
│   ├── 编程 Skill
│   ├── 自动化 Skill
│   └── Skill Factory
│
├── 4. Workflow Engine 流程引擎
│   ├── 任务拆解流程
│   ├── 文档生成流程
│   ├── 内容生产流程
│   ├── 工具调用流程
│   ├── 审批流程
│   ├── 质检流程
│   ├── 复盘流程
│   ├── Skill 创建流程
│   └── Agent 创建流程
│
├── 5. Communication 通信系统
│   ├── Agent 对 Agent 消息
│   ├── 小组会议
│   ├── 部门会议
│   ├── 董事会会议
│   ├── 任务交接
│   ├── 事件广播
│   └── 冲突仲裁
│
├── 6. Tool Layer 工具层
│   ├── 浏览器
│   ├── 文件系统
│   ├── 数据库
│   ├── API
│   ├── 邮箱
│   ├── 日历
│   ├── 文档
│   ├── 表格
│   ├── PDF
│   ├── PPT
│   ├── GitHub
│   ├── 本地电脑控制
│   ├── RPA
│   └── MCP / 插件接口
│
├── 7. Memory 记忆系统
│   ├── 短期记忆
│   ├── 长期记忆
│   ├── 用户记忆
│   ├── 项目记忆
│   ├── 任务记忆
│   ├── 成功案例
│   ├── 失败经验
│   └── 复盘记录
│
├── 8. Knowledge Base 知识库
│   ├── 公司规则
│   ├── 产品说明
│   ├── 服务流程
│   ├── 模板库
│   ├── 合同模板
│   ├── 话术模板
│   ├── 操作文档
│   ├── 行业资料
│   └── 风控规则
│
├── 9. Safety 安全风控
│   ├── 权限分级
│   ├── 审批中心
│   ├── 沙盒运行
│   ├── 回滚机制
│   ├── 内容合规
│   ├── 数据隐私
│   ├── 提示词注入防护
│   ├── 工具风险控制
│   └── 红队检查
│
├── 10. Evaluation 评测系统
│   ├── Agent 评分
│   ├── Skill 评分
│   ├── Workflow 评分
│   ├── 输出质量
│   ├── 成本统计
│   ├── 风险等级
│   └── 成功率统计
│
├── 11. Dashboard 控制台
│   ├── 任务中心
│   ├── Agent 中心
│   ├── Skill 中心
│   ├── Workflow 中心
│   ├── 审批中心
│   ├── 风控中心
│   ├── 日志中心
│   ├── 记忆中心
│   └── 系统设置
│
└── 12. Evolution 自我进化
    ├── GitHub 学习
    ├── Skill 创建
    ├── Skill 升级
    ├── Agent 创建
    ├── Agent 升级
    ├── Workflow 优化
    ├── A/B 测试
    ├── 失败复盘
    └── 新项目孵化
```

---

# 7. Agent 设计

## 7.1 Agent 是什么

Agent 是 AI 员工 / AI 岗位。

Agent 负责：

```text
理解任务
拆解任务
调用 Skill
调用工具
和其他 Agent 沟通
请求审批
检查结果
记录日志
复盘经验
```

Agent 不能直接越权。

Agent 不等于 Skill。

```text
Agent = 会思考、会判断、会分工的 AI 岗位
Skill = Agent 可以调用的具体能力
Tool = Skill 或 Agent 可以调用的外部工具
Workflow = 多个 Agent、Skill、Tool 串起来的完整流程
```

---

## 7.2 Agent 必须有身份配置

每个 Agent 必须有完整配置：

```json
{
  "agent_id": "ceo_agent_v1",
  "name": "AI CEO",
  "department": "Executive",
  "role": "负责总指挥、任务拆解、Agent 调度、结果汇总",
  "permissions": [
    "read_tasks",
    "create_tasks",
    "assign_tasks",
    "request_approval"
  ],
  "forbidden": [
    "execute_payment",
    "delete_audit_log",
    "disable_risk_system",
    "modify_root_permissions"
  ],
  "allowed_skills": [
    "task_planning_skill",
    "summary_skill",
    "decision_support_skill"
  ],
  "allowed_tools": [
    "database_read_tool",
    "task_manager_tool"
  ],
  "reports_to": "human_root",
  "risk_level": "high",
  "version": "1.0.0",
  "enabled": true
}
```

---

## 7.3 第一版基础 Agent

第一版至少要有：

```text
1. CEO Agent
2. Project Manager Agent
3. Document Agent
4. Product Agent
5. Tech Agent
6. Data Agent
7. Risk Agent
8. Legal / Compliance Agent
9. Finance Assistant Agent
10. Quality Check Agent
11. Memory Agent
12. Skill Manager Agent
13. Workflow Agent
14. Audit Agent
15. Capability Gap Detector Agent
16. Agent Factory Agent
17. Skill Factory Agent
```

第一版最关键的是：

```text
CEO Agent
Project Manager Agent
Risk Agent
Quality Check Agent
Audit Agent
Skill Manager Agent
Capability Gap Detector Agent
Agent Factory Agent
Skill Factory Agent
```

---

# 8. Skill 设计

## 8.1 Skill 是什么

Skill 是技能包 / 插件能力。

Agent 想干活，就调用 Skill。

例子：

```text
文档 Agent 调用 文档写作 Skill
技术 Agent 调用 代码生成 Skill
财务 Agent 调用 报表 Skill
风控 Agent 调用 风险检查 Skill
质量 Agent 调用 质检 Skill
```

---

## 8.2 Skill 必须注册

每个 Skill 必须有注册信息：

```json
{
  "skill_id": "document_writer_skill_v1",
  "name": "文档写作 Skill",
  "type": "document",
  "description": "根据目标和资料生成结构化文档",
  "input_schema": {
    "topic": "string",
    "audience": "string",
    "outline": "array",
    "materials": "array"
  },
  "output_schema": {
    "markdown_document": "string"
  },
  "allowed_agents": [
    "document_agent",
    "ceo_agent",
    "project_manager_agent"
  ],
  "risk_level": "low",
  "requires_approval": false,
  "version": "1.0.0",
  "enabled": true
}
```

---

## 8.3 第一版基础 Skill

第一版至少实现：

```text
1. 任务拆解 Skill
2. 文档写作 Skill
3. 总结 Skill
4. 改写 Skill
5. 风险检查 Skill
6. 质检 Skill
7. 数据整理 Skill
8. 表格生成 Skill
9. 代码生成 Skill
10. 代码审查 Skill
11. GitHub 项目分析 Skill
12. 审批请求 Skill
13. 日志记录 Skill
14. 记忆写入 Skill
15. 知识库检索 Skill
16. Skill 搜索 Skill
17. Skill 组合 Skill
18. 临时 Skill 创建 Skill
```

---

# 9. Agent / Skill 动态扩展机制

这是核心模块，必须实现。

系统不能是固定死的。

以后使用过程中，如果发现缺少 Agent 或 Skill，系统必须能识别、申请、创建、测试、审批、注册和复盘。

模块名称：

```text
Capability Gap Detector
Agent Factory
Skill Factory
Agent Registry
Skill Registry
Skill Missing Handler
Agent Missing Handler
Skill Composer
Temporary Skill Runtime
Temporary Agent Runtime
Sandbox Test Center
Evaluation Center
Version Manager
Rollback Manager
```

---

## 9.1 判断是缺 Skill 还是缺 Agent

缺 Skill：

```text
已有合适 Agent，但缺少一个具体能力。
```

例子：

```text
文档 Agent 缺少“考试题生成 Skill”
技术 Agent 缺少“数据库迁移 Skill”
数据 Agent 缺少“图表分析 Skill”
图片 Agent 缺少“Logo 设计 Skill”
```

解决：

```text
补 Skill
```

缺 Agent：

```text
系统长期反复出现某类任务，但没有专门岗位负责。
```

例子：

```text
经常需要做培训课程 → 需要 Training Agent
经常需要做招聘筛选 → 需要 Recruiting Agent
经常需要做合同审查 → 需要 Legal Agent
经常需要做数据报表 → 需要 Data Analyst Agent
经常需要做视频生产 → 需要 Video Agent
```

解决：

```text
补 Agent
```

---

## 9.2 缺 Skill 的处理流程

```text
Agent 执行任务
↓
发现缺少 Skill
↓
Skill Manager 搜索 Skill Registry
↓
找相似 Skill
↓
能替代就替代
↓
能组合就组合
↓
不能组合就创建临时 Skill
↓
常用能力申请正式 Skill
↓
进入沙盒测试
↓
风控检查
↓
质检评测
↓
低风险自动使用
↓
中风险进入审批
↓
高风险禁止或 Root 确认
↓
注册进 Skill Registry
↓
记录版本和使用效果
```

缺 Skill 的处理方式：

```text
1. 使用已有 Skill 替代
2. 多个 Skill 组合
3. 创建临时 Skill
4. 创建正式 Skill
5. 外部工具接入成 Skill
6. 高风险 Skill 拒绝或转人工
```

---

## 9.3 缺 Agent 的处理流程

```text
系统发现某类任务反复出现
↓
Capability Gap Detector 判断这是岗位缺口
↓
CEO Agent 提出新增 Agent 建议
↓
Agent Factory 生成 Agent 配置
↓
Permission System 设置权限边界
↓
Skill Manager 分配可调用 Skill
↓
Tool Manager 分配可调用 Tool
↓
Sandbox 运行模拟任务
↓
Evaluation Center 评测表现
↓
Risk Agent 检查风险
↓
需要时进入 Approval Center
↓
通过后注册进 Agent Registry
↓
正式加入 AI Company OS
↓
后续持续评分、升级、暂停或回滚
```

---

## 9.4 新 Agent 配置示例

```json
{
  "agent_id": "training_agent_v1",
  "name": "Training Agent",
  "department": "Knowledge",
  "role": "负责把资料转成课程、学习路径、测验和培训文档",
  "allowed_skills": [
    "document_summary_skill",
    "knowledge_extract_skill",
    "quiz_generator_skill",
    "course_outline_skill"
  ],
  "permissions": [
    "read_knowledge_base",
    "create_internal_document",
    "request_approval"
  ],
  "forbidden": [
    "publish_external_content_without_approval",
    "access_private_finance_data",
    "modify_root_settings",
    "delete_audit_logs"
  ],
  "risk_level": "low_to_medium",
  "version": "1.0.0",
  "enabled": false,
  "requires_human_approval_before_enable": true
}
```

---

## 9.5 自动补、审批补、禁止补

低风险能力可以自动创建临时 Skill：

```text
总结
改写
生成目录
整理文本
生成草稿
格式转换
知识点提取
内部报告
```

中风险能力必须审批：

```text
发送消息
发布内容
合同生成
报价
客户资料读取
外部 API 调用
本地电脑操作
代码执行
```

高风险能力禁止自动创建和自动执行：

```text
退款
转账
修改收款账户
删除订单
删除审计日志
关闭风控
导出全部客户隐私
绕过验证码
绕过平台限制
攻击系统
盗号
钓鱼
违法操作
```

---

## 9.6 动态扩展最终规则

```text
缺小能力 → 补 Skill
缺长期岗位 → 补 Agent
临时用一次 → 临时 Skill / 临时 Agent
以后经常用 → 注册成正式 Skill / Agent
低风险 → 可以自动
中风险 → 人工审批
高风险 → 禁止或 Root 确认
做错了 → 回滚
表现不好 → 下架或升级
表现好 → 沉淀进系统
```

这个机制是 AI Company OS 越用越完整的核心。

---

# 10. Workflow 设计

Workflow 是完整流程。

Skill 是一个能力。

Workflow 是一整套事情。

例如文档生成 Workflow：

```text
用户提出文档目标
↓
CEO Agent 理解目标
↓
Project Manager Agent 拆目录
↓
Document Agent 写正文
↓
Tech / Product / Data / Risk 等 Agent 补内容
↓
Risk Agent 检查风险
↓
Quality Agent 质检
↓
Document Agent 修改
↓
Audit Agent 记录过程
↓
提交给用户确认
↓
写入知识库
```

---

## 10.1 第一版基础 Workflow

第一版至少要有：

```text
1. 文档生成 Workflow
2. 任务拆解 Workflow
3. Agent 协作 Workflow
4. Skill 缺失处理 Workflow
5. Agent 缺失处理 Workflow
6. 审批 Workflow
7. 质检 Workflow
8. 复盘 Workflow
9. GitHub 项目分析 Workflow
10. 工具调用 Workflow
```

---

# 11. Agent 通信系统

Agent 必须能互相对话，但不能乱聊。

必须通过统一通信系统：

```text
Message Bus
Agent Chat
Meeting Room
Task Handoff
Event Broadcast
Approval Request
Conflict Arbitration
Audit Log
```

---

## 11.1 Agent 消息格式

```json
{
  "message_id": "msg_001",
  "task_id": "task_001",
  "from_agent": "document_agent",
  "to_agent": "risk_agent",
  "message_type": "risk_check_request",
  "content": "请检查这份文档是否存在夸大承诺和高风险表达",
  "priority": "medium",
  "requires_response": true,
  "created_at": "datetime"
}
```

---

## 11.2 通信类型

```text
1. 一对一消息
2. 任务交接
3. 小组会议
4. 部门会议
5. 董事会会议
6. 事件广播
7. 审批请求
8. 冲突仲裁
```

---

## 11.3 冲突仲裁

Agent 意见冲突时，不能乱决定。

例如：

```text
某 Agent 认为可以执行
财务 Agent 认为成本太高
风控 Agent 认为风险大
法务 Agent 认为边界不清
```

处理规则：

```text
安全 > 合规 > 隐私 > 用户确认 > 质量 > 成本 > 效率
```

最终：

```text
Risk Agent 可以拦截高风险动作
Legal Agent 可以拦截合规风险
CEO Agent 负责汇总
Human Root 最终决定
```

---

# 12. 任务状态机

每个任务都必须有生命周期。

状态：

```text
created 创建
planned 已规划
assigned 已分配
in_progress 执行中
waiting_skill 等待 Skill
waiting_agent 等待 Agent
waiting_tool 等待工具
needs_review 需要审查
needs_approval 需要人工确认
approved 已批准
executing 执行中
quality_checking 质检中
completed 已完成
reviewed 已复盘
```

失败状态：

```text
blocked 被风控拦截
failed 失败
paused 暂停
cancelled 取消
rollback 回滚
escalated 转人工
```

---

# 13. 权限系统

权限分 6 级。

```text
L0 只读
只能读取公开资料、系统内允许读取的数据。

L1 草稿
可以生成文案、方案、图片、视频、代码草稿。

L2 内部写入
可以创建内部任务、写入内部记录、保存草稿、写入记忆。

L3 外部低风险
可以准备外部消息、准备发布内容，但必须人工确认后才能发出。

L4 外部高风险
涉及合同、客户隐私、资金、账号、电脑操作，必须 Root 确认。

L5 Root
收款账户、退款、删除数据、关闭风控、密钥管理、真实资金动作，只能人类 Root。
```

---

# 14. 审批中心

凡是中高风险动作，都进入审批中心。

审批中心必须展示：

```text
AI 想做什么
为什么要做
涉及哪个任务
哪个 Agent 发起
调用哪个 Skill
调用哪个 Tool
风险等级
可能收益
可能损失
是否可回滚
建议批准 / 修改 / 拒绝
```

审批结果：

```text
approved 批准
rejected 拒绝
modified 修改后批准
need_more_info 需要更多信息
blocked 禁止
```

---

# 15. 安全禁止事项

严禁实现：

```text
黑产
盗号
钓鱼
诈骗
攻击
绕过验证码
绕过平台风控
窃取 token/cookie
恶意批量注册
恶意群发
广告点击作弊
自动洗钱
自动转账
非法数据抓取
恶意控制电脑
删除审计记录
关闭安全系统
```

如果用户请求这些功能，系统必须拒绝，并写入风险日志。

---

# 16. 审计日志

所有关键动作必须留痕。

日志记录：

```text
时间
用户
任务 ID
Agent ID
Skill ID
Tool ID
输入
输出
风险等级
审批状态
执行结果
错误信息
消耗成本
模型名称
版本号
```

禁止：

```text
AI 自动删除审计日志
AI 修改审计日志
AI 关闭审计系统
```

---

# 17. 记忆系统

记忆分层：

```text
短期记忆：
当前任务、当前对话、当前文档、当前项目状态。

中期记忆：
最近任务、最近失败、最近修改、最近审批。

长期记忆：
用户偏好、项目规则、成功案例、失败经验、系统架构、常用模板。
```

记忆类型：

```text
用户记忆
项目记忆
Agent 记忆
Skill 记忆
Workflow 记忆
风险记忆
复盘记忆
```

---

# 18. 知识库系统

知识库保存固定资料。

包括：

```text
项目说明
系统架构
Agent 说明
Skill 说明
Workflow 说明
权限规则
风控规则
模板
SOP
代码说明
部署说明
常见问题
复盘记录
```

Agent 做任务时，必须先检索相关知识库，不要每次从 0 开始。

---

# 19. 工具层

工具分级：

```text
只读工具：
搜索、读取文件、读取数据库、查看日志。

低风险写入：
生成草稿、写入内部任务、写入知识库。

中风险写入：
修改内部数据、调用外部 API、准备发送消息。

高风险写入：
发送外部消息、发布内容、删除数据、控制电脑、执行脚本、资金动作。
```

第一版工具：

```text
文件系统 Tool
数据库 Tool
知识库 Tool
日志 Tool
GitHub Tool
代码执行 / 测试 Tool
文档生成 Tool
表格生成 Tool
审批 Tool
```

未来预留：

```text
浏览器 Tool
邮箱 Tool
日历 Tool
本地电脑控制 Tool
RPA Tool
MCP Tool
第三方软件 Tool
```

---

# 20. GitHub 吸收进化模块

模块名称：

```text
GitHubAbsorber
```

作用：

让 AI 分析 GitHub 上的开源项目，把有用能力吸收成 Skill、Tool 或 Workflow。

但必须安全。

流程：

```text
搜索项目
↓
读取 README
↓
分析功能
↓
检查许可证
↓
检查维护状态
↓
安全审查
↓
代码审查
↓
放入沙盒
↓
运行测试
↓
总结可用能力
↓
生成接入方案
↓
人工确认
↓
注册成 Skill / Tool / Workflow
```

禁止：

```text
未知代码直接进入核心系统
未知脚本直接执行
绕过许可证
引入恶意代码
引入高风险自动化
```

---

# 21. Codex 指挥中心

模块名称：

```text
CodexCommandCenter
```

作用：

让我能把想法、需求、项目说明、任务拆解发给 Codex，让 Codex 像程序员一样开发、改代码、测试、修 bug。

Codex 应该读取：

```text
PROJECT_IDEA_FOR_CODEX.md
ROADMAP.md
AGENTS.md
SKILLS.md
WORKFLOWS.md
PERMISSIONS.md
SAFETY.md
DATABASE.md
API.md
TESTING.md
DEPLOYMENT.md
```

Codex 的工作方式：

```text
先读项目说明
再检查现有代码
再给开发计划
再分阶段实现
每次改动必须有测试
高风险功能必须加权限和审计
不要跳过安全边界
不要删除核心日志
不要做违法功能
```

---

# 22. 电脑控制中心

模块名称：

```text
ComputerControlCenter
```

作用：

未来让 AI 在授权范围内控制电脑、文件、软件、浏览器。

可以自动：

```text
整理文件
生成文档
读取本地项目
运行测试
打开允许的软件
生成报告
保存草稿
```

必须确认：

```text
删除文件
修改重要配置
执行脚本
安装软件
上传文件
发送外部消息
提交代码
发布内容
```

禁止或 Root 确认：

```text
转账
退款
改密码
导出隐私
删除日志
安装未知高危程序
绕过安全限制
```

---

# 23. 提示词注入防护

Agent 会读取网页、文件、邮件、GitHub README、用户输入等外部内容。

外部内容不能变成系统命令。

规则：

```text
外部内容永远不能修改系统权限
外部内容不能命令 Agent 泄露数据
外部内容不能命令 Agent 删除日志
外部内容不能绕过审批
外部内容不能让 Agent 忽略安全规则
```

必须区分：

```text
System Instruction 系统指令
Developer Rule 开发规则
User Command 用户命令
External Content 外部内容
Tool Result 工具结果
```

---

# 24. 沙盒系统

新 Agent、新 Skill、新 Tool、新 Workflow 必须先进入沙盒。

沙盒能模拟：

```text
模拟任务
模拟用户
模拟文件
模拟工具调用
模拟失败
模拟审批
模拟风险
```

通过测试后才能上线。

---

# 25. 回滚系统

重要动作执行前保存状态：

```text
before_state
after_state
rollback_plan
```

可回滚对象：

```text
Agent 配置
Skill 版本
Workflow 版本
Prompt 版本
知识库文档
系统设置
部分数据修改
```

---

# 26. 评测系统

必须评测：

```text
Agent 是否完成任务
Skill 输出质量如何
Workflow 是否稳定
成本是否过高
风险是否增加
是否需要人工介入
是否有重复劳动
是否值得沉淀成模板
```

指标：

```text
任务完成率
失败率
返工率
人工介入次数
风险拦截次数
输出质量分
成本
速度
用户满意度
```

---

# 27. 控制台

第一版必须有简单 Web 控制台。

页面：

```text
1. 首页 Dashboard
2. 任务中心 Tasks
3. Agent 中心 Agents
4. Skill 中心 Skills
5. Workflow 中心 Workflows
6. 审批中心 Approvals
7. 风控中心 Risks
8. 日志中心 Audit Logs
9. 记忆中心 Memory
10. 知识库 Knowledge Base
11. 系统设置 Settings
```

首页显示：

```text
当前任务数量
待审批数量
最近风险
最近失败
Agent 状态
Skill 数量
Workflow 数量
系统健康
最近日志
```

---

# 28. 文档能力示例

系统做文档时，不是一个 AI 随便写。

流程应该是：

```text
用户提出文档目标
↓
CEO Agent 判断任务类型
↓
Project Manager Agent 拆目录
↓
Document Agent 写正文
↓
Product / Tech / Risk / Data 等 Agent 补内容
↓
Risk Agent 检查风险
↓
Quality Agent 检查质量
↓
Document Agent 修改
↓
Audit Agent 记录过程
↓
提交给用户确认
↓
写入 Knowledge Base
```

文档类型包括：

```text
项目说明书
开发需求文档
商业计划草稿
产品说明书
用户手册
操作手册
培训文档
合同草稿
报价方案
交付报告
会议纪要
复盘报告
日报周报月报
技术架构文档
数据库设计文档
API 文档
给 Codex 的开发任务文档
```

---

# 29. 数据库表

建议第一版数据库包含：

```text
users
roles
permissions

agents
agent_versions
agent_permissions
agent_messages
agent_meetings

skills
skill_versions
skill_permissions
skill_requests
skill_runs
skill_test_results

workflows
workflow_runs
workflow_steps

tasks
task_states
events

approvals
approval_logs

audit_logs
traces
risk_logs
quality_checks
evaluations

memories
knowledge_docs

tools
tool_permissions
tool_runs

model_usage
cost_logs

incidents
backups
```

---

# 30. 推荐代码目录

```text
ai-company-os/
│
├── apps/
│   ├── web_dashboard/
│   └── admin_console/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   │
│   │   ├── core/
│   │   │   ├── agent_runtime/
│   │   │   ├── skill_runtime/
│   │   │   ├── workflow_engine/
│   │   │   ├── event_bus/
│   │   │   ├── state_machine/
│   │   │   ├── scheduler/
│   │   │   └── model_gateway/
│   │   │
│   │   ├── agents/
│   │   │   ├── executive/
│   │   │   ├── project/
│   │   │   ├── document/
│   │   │   ├── tech/
│   │   │   ├── data/
│   │   │   ├── risk/
│   │   │   ├── legal/
│   │   │   ├── quality/
│   │   │   ├── factory/
│   │   │   └── system/
│   │   │
│   │   ├── skills/
│   │   │   ├── registry.py
│   │   │   ├── manager.py
│   │   │   ├── factory.py
│   │   │   ├── composer.py
│   │   │   ├── missing_handler.py
│   │   │   ├── sandbox.py
│   │   │   ├── evaluator.py
│   │   │   ├── document/
│   │   │   ├── content/
│   │   │   ├── data/
│   │   │   ├── code/
│   │   │   └── automation/
│   │   │
│   │   ├── workflows/
│   │   │   ├── task_planning/
│   │   │   ├── document_generation/
│   │   │   ├── approval_flow/
│   │   │   ├── quality_check/
│   │   │   ├── skill_creation/
│   │   │   ├── agent_creation/
│   │   │   └── github_ingestion/
│   │   │
│   │   ├── tools/
│   │   │   ├── filesystem/
│   │   │   ├── database/
│   │   │   ├── github/
│   │   │   ├── documents/
│   │   │   ├── browser/
│   │   │   └── local_computer/
│   │   │
│   │   ├── memory/
│   │   ├── knowledge_base/
│   │   ├── safety/
│   │   ├── permissions/
│   │   ├── approvals/
│   │   ├── audit/
│   │   ├── evaluations/
│   │   ├── incidents/
│   │   └── api/
│   │
│   ├── tests/
│   └── migrations/
│
├── frontend/
│   ├── app/
│   ├── components/
│   ├── pages/
│   └── lib/
│
├── docs/
│   ├── PROJECT_IDEA_FOR_CODEX.md
│   ├── ROADMAP.md
│   ├── AGENTS.md
│   ├── SKILLS.md
│   ├── WORKFLOWS.md
│   ├── PERMISSIONS.md
│   ├── SAFETY.md
│   ├── DATABASE.md
│   ├── API.md
│   ├── TESTING.md
│   └── DEPLOYMENT.md
│
├── docker-compose.yml
├── README.md
└── .env.example
```

---

# 31. 技术栈建议

第一版建议：

```text
后端：
Python + FastAPI

前端：
Next.js + TypeScript

数据库：
PostgreSQL

向量记忆：
pgvector

任务队列：
Redis

测试：
pytest + frontend typecheck + e2e smoke test

部署：
Docker Compose

日志：
结构化 JSON logs

权限：
RBAC + Risk Level + Approval Policy
```

---

# 32. 第一版最小完整闭环

第一版必须能跑通：

```text
1. 用户登录
2. 创建任务
3. CEO Agent 拆任务
4. Project Manager 分配任务
5. Document Agent 调用文档 Skill
6. 如果缺 Skill，进入 Skill Missing Handler
7. 如果缺 Agent，进入 Agent Missing Handler / Agent Factory
8. Risk Agent 检查风险
9. Quality Agent 质检
10. 如果需要审批，进入 Approval Center
11. 审批后完成任务
12. 全过程写入 Audit Log
13. 结果写入 Memory / Knowledge Base
14. Dashboard 能看到任务、Agent、Skill、审批、日志
```

---

# 33. 第一版必须实现的 API

```text
POST /auth/register
POST /auth/login
POST /auth/logout

GET /agents
POST /agents
GET /agents/{id}
POST /agents/missing
POST /agents/factory/create

GET /skills
POST /skills
POST /skills/search
POST /skills/missing
POST /skills/factory/create

GET /workflows
POST /workflows/run

GET /tasks
POST /tasks
GET /tasks/{id}
POST /tasks/{id}/run
POST /tasks/{id}/pause
POST /tasks/{id}/cancel

GET /approvals
POST /approvals/{id}/approve
POST /approvals/{id}/reject

GET /audit-logs

GET /memory
POST /memory

GET /knowledge
POST /knowledge

GET /risks

GET /dashboard/summary
```

---

# 34. 第一版必须有的测试

```text
1. 权限测试
2. 审批测试
3. 风控拦截测试
4. 任务状态机测试
5. Agent 注册测试
6. Skill 注册测试
7. Skill 缺失处理测试
8. Agent 缺失处理测试
9. Workflow 执行测试
10. 审计日志测试
11. 记忆写入测试
12. 知识库写入测试
13. API smoke test
14. 前端构建测试
```

关键测试：

```text
AI 不能自动退款
AI 不能删除审计日志
AI 不能关闭风控
AI 不能修改 Root 权限
AI 不能自动执行高危工具
外部写入动作必须进入审批
缺 Skill 时不能直接失败，必须进入缺失处理流程
缺 Agent 时不能乱创建，必须进入 Agent Factory 和审批流程
```

---

# 35. 未来扩展模块

第一版预留接口，后续可以扩展：

```text
AI 图片生成生产线
AI 视频生成生产线
AI 音频 / 配音 / 字幕
多项目管理
多租户
移动端 App
本地电脑控制
MCP 工具市场
更多第三方 API
商业计费
客户 CRM
订单交付
更多行业模板
自动化测试强化
Agent 自我评测
更复杂的 GitHub 吸收系统
更复杂的电脑控制系统
```

---

# 36. Codex 开发要求

请 Codex 不要只写一个 Demo。

要按照这个目标开发：

```text
可运行
可测试
可扩展
有权限
有审批
有风控
有审计
有任务状态
有 Agent 注册
有 Skill 注册
有 Workflow
有 Dashboard
有缺 Skill 处理
有缺 Agent 处理
```

每次开发请遵守：

```text
1. 先读文档
2. 再检查现有代码
3. 再给开发计划
4. 再分阶段改代码
5. 每个阶段跑测试
6. 再说明改了什么
7. 高风险动作必须加权限、审批、审计
8. 不要删除安全模块
9. 不要绕过风控
10. 不要实现违法功能
```

---

# 37. 最终目标

我要最终得到的是：

```text
一个通用 AI 公司操作系统。
它不是一个死工具，而是一个会扩展的系统。
它能把完整公司的岗位变成 Agent。
它能把岗位能力变成 Skill。
它能把复杂事情变成 Workflow。
它能让 Agent 互相沟通、开会、交接、反对、仲裁。
它能在缺 Skill 时补 Skill。
它能在缺 Agent 时补 Agent。
它能接入工具。
它能吸收 GitHub 上有用的开源能力。
它能用 Memory 保存经验。
它能用 Knowledge Base 保存规则和模板。
它能用 Permission 和 Approval 控制危险动作。
它能用 Risk System 防止翻车。
它能用 Audit Log 记录所有行为。
它能用 Evaluation 评测 Agent、Skill、Workflow。
它能通过 Dashboard 让我作为 Human Root 控制全局。
```

Human Root 永远拥有最高权限。

AI 可以越来越强，但不能越权。

安全、审计、审批、风控，必须从第一版就存在。
