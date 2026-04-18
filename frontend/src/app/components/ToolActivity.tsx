import { FileText, Terminal, Clock } from "lucide-react";

export function ToolActivity() {
  const activities = [
    {
      type: "file",
      action: "读取",
      target: "data/customer_feedback.json",
      time: "10:23:17",
      status: "success",
    },
    {
      type: "terminal",
      action: "执行",
      target: "sentiment_analysis.py",
      time: "10:23:18",
      status: "running",
    },
    {
      type: "file",
      action: "写入",
      target: "output/analysis_results.json",
      time: "10:23:19",
      status: "pending",
    },
  ];

  return (
    <div className="h-full bg-[#161B22] flex flex-col">
      <div className="h-10 border-b border-gray-800 flex items-center px-3">
        <span className="text-sm font-medium text-gray-300">工具活动</span>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {activities.map((activity, idx) => (
          <div
            key={idx}
            className={`p-3 rounded-lg border ${
              activity.status === "success"
                ? "bg-green-950/20 border-green-800"
                : activity.status === "running"
                ? "bg-blue-950/20 border-blue-700 animate-pulse"
                : "bg-gray-800/20 border-gray-700"
            }`}
          >
            <div className="flex items-start gap-2">
              <div
                className={`mt-0.5 ${
                  activity.type === "file"
                    ? "text-blue-400"
                    : "text-purple-400"
                }`}
              >
                {activity.type === "file" ? (
                  <FileText className="w-4 h-4" />
                ) : (
                  <Terminal className="w-4 h-4" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm text-gray-200 mb-1">
                  <span className="font-medium">{activity.action}</span>
                </div>
                <div className="text-xs text-gray-400 truncate">
                  {activity.target}
                </div>
                <div className="flex items-center gap-1 mt-1 text-xs text-gray-500">
                  <Clock className="w-3 h-3" />
                  {activity.time}
                </div>
              </div>
              <div
                className={`px-2 py-1 rounded text-xs font-medium ${
                  activity.status === "success"
                    ? "bg-green-600/20 text-green-400"
                    : activity.status === "running"
                    ? "bg-blue-600/20 text-blue-400"
                    : "bg-gray-600/20 text-gray-400"
                }`}
              >
                {activity.status === "success"
                  ? "完成"
                  : activity.status === "running"
                  ? "运行中"
                  : "待执行"}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
