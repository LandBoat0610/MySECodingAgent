import {
  TrendingUp,
  Clock,
  Zap,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";

export function DashboardPage() {
  const summaryCards = [
    {
      title: "平均任务成功率",
      value: "87.3%",
      icon: TrendingUp,
      color: "text-green-400",
      bgColor: "bg-green-950/30",
      borderColor: "border-green-700",
    },
    {
      title: "平均Token使用量",
      value: "2,345",
      icon: Zap,
      color: "text-blue-400",
      bgColor: "bg-blue-950/30",
      borderColor: "border-blue-700",
    },
    {
      title: "平均响应时间",
      value: "1.8s",
      icon: Clock,
      color: "text-amber-400",
      bgColor: "bg-amber-950/30",
      borderColor: "border-amber-700",
    },
  ];

  const evaluations = [
    {
      task: "客户反馈分析",
      agent: "ReAct",
      dataset: "CustomerFeedback-2026",
      status: "success",
    },
    {
      task: "代码漏洞检测",
      agent: "Reflexion",
      dataset: "SecurityAudit-v3",
      status: "success",
    },
    {
      task: "文档自动生成",
      agent: "ReAct",
      dataset: "TechDocs-Sample",
      status: "failed",
    },
    {
      task: "数据清洗任务",
      agent: "Reflexion",
      dataset: "DataQuality-Test",
      status: "success",
    },
  ];

  const ragasData = [
    { metric: "答案相关性", score: 0.89 },
    { metric: "忠实度", score: 0.92 },
    { metric: "上下文相关性", score: 0.85 },
    { metric: "上下文精确度", score: 0.88 },
    { metric: "答案正确性", score: 0.86 },
  ];

  const agentComparison = [
    { name: "成功率", ReAct: 84, Reflexion: 91 },
    { name: "Token效率", ReAct: 78, Reflexion: 85 },
    { name: "响应速度", ReAct: 92, Reflexion: 76 },
    { name: "准确度", ReAct: 86, Reflexion: 89 },
  ];

  return (
    <div className="h-full w-full overflow-auto bg-[#0D1117] p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {summaryCards.map((card, idx) => (
            <div
              key={idx}
              className={`${card.bgColor} border-2 ${card.borderColor} rounded-lg p-5`}
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm text-gray-400 mb-1">
                    {card.title}
                  </div>
                  <div className={`text-3xl font-bold ${card.color}`}>
                    {card.value}
                  </div>
                </div>
                <card.icon className={`w-10 h-10 ${card.color}`} />
              </div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Evaluation List */}
          <div className="bg-[#161B22] border border-gray-800 rounded-lg overflow-hidden">
            <div className="border-b border-gray-800 p-4">
              <h2 className="text-lg font-semibold text-gray-200">
                评估任务列表
              </h2>
            </div>
            <div className="p-4">
              <div className="space-y-3">
                {evaluations.map((evaluation, idx) => (
                  <div
                    key={idx}
                    className="bg-gray-800/40 border border-gray-700 rounded-lg p-4 hover:border-blue-600 transition-colors"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1">
                        <h3 className="text-sm font-medium text-gray-200 mb-1">
                          {evaluation.task}
                        </h3>
                        <div className="flex items-center gap-3 text-xs text-gray-400">
                          <span>代理: {evaluation.agent}</span>
                          <span>•</span>
                          <span>{evaluation.dataset}</span>
                        </div>
                      </div>
                      {evaluation.status === "success" ? (
                        <div className="flex items-center gap-1 bg-green-600/20 text-green-400 px-2 py-1 rounded text-xs font-medium">
                          <CheckCircle2 className="w-3 h-3" />
                          成功
                        </div>
                      ) : (
                        <div className="flex items-center gap-1 bg-red-600/20 text-red-400 px-2 py-1 rounded text-xs font-medium">
                          <XCircle className="w-3 h-3" />
                          失败
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Ragas Metrics Radar */}
          <div className="bg-[#161B22] border border-gray-800 rounded-lg overflow-hidden">
            <div className="border-b border-gray-800 p-4">
              <h2 className="text-lg font-semibold text-gray-200">
                Ragas质量指标
              </h2>
            </div>
            <div className="p-4">
              <ResponsiveContainer width="100%" height={300}>
                <RadarChart data={ragasData}>
                  <PolarGrid stroke="#374151" />
                  <PolarAngleAxis
                    dataKey="metric"
                    tick={{ fill: "#9CA3AF", fontSize: 12 }}
                  />
                  <PolarRadiusAxis
                    angle={90}
                    domain={[0, 1]}
                    tick={{ fill: "#9CA3AF" }}
                  />
                  <Radar
                    name="得分"
                    dataKey="score"
                    stroke="#3B82F6"
                    fill="#3B82F6"
                    fillOpacity={0.6}
                  />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Agent Comparison */}
        <div className="bg-[#161B22] border border-gray-800 rounded-lg overflow-hidden">
          <div className="border-b border-gray-800 p-4">
            <h2 className="text-lg font-semibold text-gray-200">
              代理性能对比
            </h2>
          </div>
          <div className="p-4">
            <ResponsiveContainer width="100%" height={350}>
              <BarChart data={agentComparison}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="name" tick={{ fill: "#9CA3AF" }} />
                <YAxis tick={{ fill: "#9CA3AF" }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#1F2937",
                    border: "1px solid #374151",
                    borderRadius: "0.5rem",
                  }}
                  labelStyle={{ color: "#F9FAFB" }}
                />
                <Legend wrapperStyle={{ color: "#9CA3AF" }} />
                <Bar dataKey="ReAct" fill="#3B82F6" radius={[8, 8, 0, 0]} />
                <Bar dataKey="Reflexion" fill="#8B5CF6" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}
