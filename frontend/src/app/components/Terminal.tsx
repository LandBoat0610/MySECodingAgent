import { Terminal as TerminalIcon } from "lucide-react";

export function Terminal() {
  const terminalOutput = [
    { type: "command", text: "$ python src/agents/react_agent.py --task 'Analyze customer feedback'" },
    { type: "output", text: "[2026-04-18 10:23:15] INFO: 初始化ReAct代理..." },
    { type: "output", text: "[2026-04-18 10:23:16] INFO: 加载工具: FileReader, CodeExecutor" },
    { type: "success", text: "[2026-04-18 10:23:17] SUCCESS: 代理初始化完成" },
    { type: "output", text: "" },
    { type: "output", text: "思考: 我需要首先读取客户反馈数据文件" },
    { type: "output", text: "行动: FileReader(\"data/customer_feedback.json\")" },
    { type: "output", text: "观察: 成功读取 1,234 条客户反馈记录" },
    { type: "output", text: "" },
    { type: "output", text: "思考: 现在我需要分析情感倾向" },
    { type: "success", text: "✓ 任务完成 - 发现 87% 正面反馈, 13% 需要改进" },
    { type: "command", text: "$ █" },
  ];

  return (
    <div className="h-full bg-[#0D1117] border-t border-gray-800 flex flex-col font-mono text-sm">
      <div className="h-9 border-b border-gray-800 flex items-center px-3 bg-[#161B22] gap-2">
        <TerminalIcon className="w-4 h-4 text-gray-400" />
        <span className="text-xs text-gray-400">终端</span>
      </div>
      <div className="flex-1 overflow-auto p-3 space-y-1">
        {terminalOutput.map((line, idx) => (
          <div
            key={idx}
            className={
              line.type === "command"
                ? "text-green-400"
                : line.type === "success"
                ? "text-emerald-400"
                : line.type === "error"
                ? "text-red-400"
                : "text-gray-300"
            }
          >
            {line.text}
          </div>
        ))}
      </div>
    </div>
  );
}
