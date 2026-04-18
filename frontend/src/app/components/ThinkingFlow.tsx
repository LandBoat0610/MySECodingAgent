import { Lightbulb, ArrowDown, CheckCircle2 } from "lucide-react";

export function ThinkingFlow() {
  const steps = [
    {
      type: "plan",
      label: "规划",
      content: "分析客户反馈数据",
      status: "completed",
    },
    {
      type: "execute",
      label: "执行",
      content: "读取JSON文件并解析",
      status: "completed",
    },
    {
      type: "reflect",
      label: "反思",
      content: "检查数据质量与完整性",
      status: "active",
    },
    {
      type: "plan",
      label: "规划",
      content: "设计情感分析策略",
      status: "pending",
    },
  ];

  return (
    <div className="h-full bg-[#161B22] flex flex-col">
      <div className="h-10 border-b border-gray-800 flex items-center px-3">
        <Lightbulb className="w-4 h-4 text-amber-400 mr-2" />
        <span className="text-sm font-medium text-gray-300">思维空间</span>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <div className="space-y-2">
          {steps.map((step, idx) => (
            <div key={idx}>
              <div
                className={`rounded-lg p-3 border-2 ${
                  step.status === "completed"
                    ? "bg-green-950/30 border-green-700"
                    : step.status === "active"
                    ? "bg-amber-950/30 border-amber-500 animate-pulse"
                    : "bg-gray-800/30 border-gray-700"
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <div
                    className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold ${
                      step.type === "plan"
                        ? "bg-blue-600 text-white"
                        : step.type === "execute"
                        ? "bg-purple-600 text-white"
                        : "bg-amber-600 text-white"
                    }`}
                  >
                    {step.type === "plan"
                      ? "P"
                      : step.type === "execute"
                      ? "E"
                      : "R"}
                  </div>
                  <span className="text-xs font-medium text-gray-400 uppercase">
                    {step.label}
                  </span>
                  {step.status === "completed" && (
                    <CheckCircle2 className="w-4 h-4 text-green-400 ml-auto" />
                  )}
                </div>
                <p className="text-sm text-gray-200 ml-8">{step.content}</p>
              </div>
              {idx < steps.length - 1 && (
                <div className="flex justify-center py-1">
                  <ArrowDown className="w-4 h-4 text-gray-600" />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
