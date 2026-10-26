import type { SurveyQuestion } from "./types";

const wellbeingOptions = [
  { value: "5", label: "所有时间" },
  { value: "4", label: "大部分时间" },
  { value: "3", label: "超过一半时间" },
  { value: "2", label: "少于一半时间" },
  { value: "1", label: "偶尔" },
  { value: "0", label: "从未" },
  { value: "prefer_not", label: "暂不回答" },
];

export const onboardingSteps: Array<{
  eyebrow: string;
  title: string;
  description: string;
  questions: SurveyQuestion[];
}> = [
  {
    eyebrow: "从认识你开始",
    title: "基础信息",
    description: "这些信息只用于建立唯一档案，并帮助老师在获得授权后与你联系。",
    questions: [
      { id: "name", type: "short_text", label: "姓名", required: true, maxLength: 80 },
      { id: "email", type: "short_text", label: "常用邮箱", description: "建议填写校内邮箱", required: true, maxLength: 320 },
      { id: "student_number", type: "short_text", label: "学号", required: true, maxLength: 40 },
      { id: "major", type: "short_text", label: "专业或培养方向", required: true, maxLength: 120 },
      {
        id: "year_level",
        type: "single",
        label: "所在年级",
        required: true,
        options: ["大一", "大二", "大三", "大四", "研究生", "其他"].map((label) => ({ value: label, label })),
      },
    ],
  },
  {
    eyebrow: "你此刻在哪里",
    title: "学习与参与现状",
    description: "没有标准答案，真实的节奏比“看起来很优秀”更有帮助。",
    questions: [
      {
        id: "current_learning",
        type: "multiple",
        label: "你最近主要在投入哪些方向？",
        required: true,
        options: ["专业课程", "语言与标化考试", "科研训练", "竞赛", "实习与职业技能", "人文艺术", "运动健康", "还在探索"].map((label) => ({ value: label, label })),
      },
      { id: "current_courses", type: "long_text", label: "可选：最近最想学好或最困扰你的内容", maxLength: 500 },
      {
        id: "weekly_load",
        type: "single",
        label: "你目前的时间和任务负荷更接近哪种状态？",
        required: true,
        options: ["比较轻松", "基本平衡", "有些忙碌", "经常超负荷", "难以判断"].map((label) => ({ value: label, label })),
      },
      {
        id: "clubs",
        type: "multiple",
        label: "你目前参与了哪些校园组织或活动？",
        required: true,
        description: "若承担组织工作，可同时选择“组织者/负责人”。",
        options: ["学术科研", "创新创业", "文体艺术", "志愿公益", "学生工作", "运动社群", "校外实践", "组织者/负责人", "暂未参加"].map((label) => ({ value: label, label })),
      },
    ],
  },
  {
    eyebrow: "什么会吸引你",
    title: "兴趣与活动偏好",
    description: "我们会用这些偏好减少无关推送，也为不同类型的同学设计活动。",
    questions: [
      {
        id: "interest_topics",
        type: "multiple",
        label: "你愿意了解哪些主题？",
        required: true,
        options: ["保研与科研", "考研规划", "出国交流", "行业与就业", "创新创业", "AI 与科技", "人文艺术", "城市探索", "心理与成长", "运动健康", "公益与社会参与"].map((label) => ({ value: label, label })),
      },
      {
        id: "activity_formats",
        type: "multiple",
        label: "你偏好的活动形式是？",
        required: true,
        options: ["短讲座", "深度工作坊", "圆桌/小组交流", "实验室或企业参访", "长期项目", "社团体验", "一对一咨询", "线上资源"].map((label) => ({ value: label, label })),
      },
      {
        id: "available_times",
        type: "multiple",
        label: "你通常方便参加活动的时段？",
        required: true,
        options: ["工作日午间", "工作日下午", "工作日晚上", "周六", "周日", "时间不固定"].map((label) => ({ value: label, label })),
      },
      {
        id: "participation_constraints",
        type: "multiple",
        label: "哪些因素可能影响你参加活动？",
        required: true,
        options: ["课程冲突", "任务太多", "地点/交通", "费用", "不认识其他人", "不确定是否适合", "需要无障碍支持", "没有明显限制"].map((label) => ({ value: label, label })),
      },
    ],
  },
  {
    eyebrow: "想去向哪里",
    title: "目标与期待",
    description: "目标可以改变。我们关心的是现在什么对你最重要，以及可以如何支持你。",
    questions: [
      {
        id: "long_term_goals",
        type: "multiple",
        label: "你目前考虑的长期方向有哪些？",
        required: true,
        options: ["保研", "考研", "出国/境深造", "直接就业", "公务员/选调", "创新创业", "学术研究", "还在探索"].map((label) => ({ value: label, label })),
      },
      {
        id: "semester_goals",
        type: "multiple",
        label: "这学期你最希望推进什么？",
        required: true,
        options: ["提升课程成绩", "通过重要考试", "进入实验室", "完成科研成果", "参加竞赛", "找到实习", "加入/建设社团", "改善作息与状态", "扩大社交连接"].map((label) => ({ value: label, label })),
      },
      {
        id: "next_30_days",
        type: "single",
        label: "未来 30 天最需要迈出的第一步是？",
        required: true,
        options: ["获得信息与路径", "制定计划", "找到同伴", "联系导师/学长姐", "报名一次活动", "完成一个具体任务", "先恢复精力", "暂时不确定"].map((label) => ({ value: label, label })),
      },
      {
        id: "barriers",
        type: "multiple",
        label: "目前最主要的阻碍是什么？",
        required: true,
        options: ["信息不足", "不知道从哪里开始", "时间管理", "行动动力", "能力准备", "资源或机会", "缺少同伴", "压力或情绪", "没有明显阻碍"].map((label) => ({ value: label, label })),
      },
      {
        id: "desired_support",
        type: "multiple",
        label: "你希望书院提供哪些支持？",
        required: true,
        options: ["经验分享", "路线规划", "技能训练", "导师/学长姐连接", "同伴小组", "实践机会", "心理成长活动", "安静的自主探索空间"].map((label) => ({ value: label, label })),
      },
    ],
  },
  {
    eyebrow: "以适合你的方式前进",
    title: "自我调节与近两周状态",
    description: "这一部分不用于诊断。你可以对任何状态问题选择“暂不回答”。",
    questions: [
      {
        id: "self_regulation",
        type: "matrix",
        label: "下面这些描述与你目前的状态有多相符？",
        description: "1 代表很不符合，5 代表非常符合。",
        required: true,
        min: 1,
        max: 5,
        minLabel: "很不符合",
        maxLabel: "非常符合",
        items: [
          { id: "planning", label: "我会把大目标拆成可执行的小步骤" },
          { id: "time_management", label: "我通常能为重要任务留出时间" },
          { id: "persistence", label: "遇到困难时，我通常能调整方法继续推进" },
          { id: "help_seeking", label: "需要时，我愿意主动向他人求助" },
          { id: "self_efficacy", label: "我相信自己有能力逐步实现当前目标" },
        ],
      },
      { id: "who5_cheerful", type: "single", label: "过去两周，我感到心情愉快、精神良好", sensitive: true, options: wellbeingOptions },
      { id: "who5_calm", type: "single", label: "过去两周，我感到平静、放松", sensitive: true, options: wellbeingOptions },
      { id: "who5_active", type: "single", label: "过去两周，我感到充满活力", sensitive: true, options: wellbeingOptions },
      { id: "who5_rested", type: "single", label: "过去两周，我醒来时感到清新、休息充分", sensitive: true, options: wellbeingOptions },
      { id: "who5_interested", type: "single", label: "过去两周，我的日常生活中有令我感兴趣的事情", sensitive: true, options: wellbeingOptions },
      {
        id: "stress_level",
        type: "single",
        label: "你最近的整体压力感受是？",
        sensitive: true,
        options: ["很低", "较低", "适中", "较高", "很高", "暂不回答"].map((label) => ({ value: label, label })),
      },
      {
        id: "belonging",
        type: "single",
        label: "你在学校或书院中感到有归属和连接吗？",
        sensitive: true,
        options: ["很少", "偶尔", "一般", "大多数时候", "非常强", "暂不回答"].map((label) => ({ value: label, label })),
      },
    ],
  },
];
