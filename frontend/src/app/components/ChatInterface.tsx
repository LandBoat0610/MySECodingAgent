import { Send, User, Bot } from "lucide-react";

export function ChatInterface() {
  const messages = [
    {
      role: "user",
      content: "请帮我分析customer_feedback.json文件中的情感倾向",
    },
    {
      role: "assistant",
      content: "好的，我会读取该文件并进行情感分析。让我开始执行任务。",
    },
    {
      role: "user",
      content: "重点关注负面反馈，并提供改进建议",
    },
  ];

  return (
    <div className="h-full bg-[#161B22] flex flex-col">
      <div className="h-10 border-b border-gray-800 flex items-center px-3">
        <span className="text-sm font-medium text-gray-300">指令对话</span>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, idx) => (
          <div key={idx} className="flex gap-3">
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                msg.role === "user" ? "bg-blue-600" : "bg-purple-600"
              }`}
            >
              {msg.role === "user" ? (
                <User className="w-4 h-4 text-white" />
              ) : (
                <Bot className="w-4 h-4 text-white" />
              )}
            </div>
            <div className="flex-1">
              <div className="text-xs text-gray-400 mb-1">
                {msg.role === "user" ? "用户" : "AI助手"}
              </div>
              <div className="text-sm text-gray-200 bg-gray-800/50 rounded-lg p-3">
                {msg.content}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="border-t border-gray-800 p-4">
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="输入指令..."
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button className="bg-blue-600 hover:bg-blue-700 text-white rounded-lg px-4 py-2 flex items-center gap-2 transition-colors">
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
