export function CodeEditor() {
  const codeContent = `# react_agent.py
import os
from typing import List, Dict
from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import Tool
from langchain_openai import ChatOpenAI

class ReActAgent:
    """基于ReAct模式的AI代理实现"""

    def __init__(self, model_name: str = "gpt-4"):
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=0.7
        )
        self.tools = self._initialize_tools()
        self.agent = self._create_agent()

    def _initialize_tools(self) -> List[Tool]:
        """初始化代理工具集"""
        return [
            Tool(
                name="FileReader",
                func=self._read_file,
                description="读取指定文件的内容"
            ),
            Tool(
                name="CodeExecutor",
                func=self._execute_code,
                description="在安全沙箱中执行Python代码"
            ),
        ]

    def _read_file(self, file_path: str) -> str:
        """读取文件内容"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"错误: {str(e)}"

    def _execute_code(self, code: str) -> str:
        """执行代码并返回结果"""
        # 实现代码执行逻辑
        pass

    def run(self, task: str) -> Dict:
        """执行任务"""
        result = self.agent.invoke({"input": task})
        return result`;

  return (
    <div className="h-full bg-[#0D1117] flex flex-col font-mono text-sm">
      <div className="h-10 border-b border-gray-800 flex items-center px-4 gap-3 bg-[#161B22]">
        <span className="text-xs text-gray-400">src/agents/react_agent.py</span>
        <div className="flex-1" />
        <span className="text-xs text-gray-500">Python</span>
      </div>
      <div className="flex-1 overflow-auto">
        <div className="p-4">
          <pre className="text-gray-300 leading-relaxed">
            {codeContent.split('\n').map((line, idx) => (
              <div key={idx} className="flex">
                <span className="text-gray-600 select-none w-12 text-right pr-4 flex-shrink-0">
                  {idx + 1}
                </span>
                <span className="flex-1">
                  {line.startsWith('#') ? (
                    <span className="text-gray-500">{line}</span>
                  ) : line.includes('import ') || line.includes('from ') ? (
                    <span className="text-purple-400">{line}</span>
                  ) : line.includes('class ') || line.includes('def ') ? (
                    <span className="text-blue-400">{line}</span>
                  ) : line.includes('"""') || line.includes("'''") ? (
                    <span className="text-green-400">{line}</span>
                  ) : line.includes('self.') ? (
                    <span className="text-cyan-400">{line}</span>
                  ) : line.includes('return ') || line.includes('try:') || line.includes('except ') ? (
                    <span className="text-pink-400">{line}</span>
                  ) : line.includes('"') || line.includes("'") ? (
                    <span className="text-amber-300">{line}</span>
                  ) : (
                    <span>{line || ' '}</span>
                  )}
                </span>
              </div>
            ))}
          </pre>
        </div>
      </div>
    </div>
  );
}
