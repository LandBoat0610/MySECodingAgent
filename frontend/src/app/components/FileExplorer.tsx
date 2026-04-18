import { Folder, ChevronRight, ChevronDown, FileCode, File } from "lucide-react";
import { useState } from "react";

interface FileNode {
  name: string;
  type: "file" | "folder";
  children?: FileNode[];
}

const fileTree: FileNode[] = [
  {
    name: "src",
    type: "folder",
    children: [
      {
        name: "agents",
        type: "folder",
        children: [
          { name: "react_agent.py", type: "file" },
          { name: "reflexion_agent.py", type: "file" },
        ],
      },
      {
        name: "evaluators",
        type: "folder",
        children: [
          { name: "ragas_eval.py", type: "file" },
          { name: "metrics.py", type: "file" },
        ],
      },
      { name: "main.py", type: "file" },
      { name: "utils.py", type: "file" },
    ],
  },
  {
    name: "tests",
    type: "folder",
    children: [
      { name: "test_agent.py", type: "file" },
      { name: "test_eval.py", type: "file" },
    ],
  },
  { name: "requirements.txt", type: "file" },
  { name: "README.md", type: "file" },
];

function FileTreeNode({ node, level = 0 }: { node: FileNode; level?: number }) {
  const [isOpen, setIsOpen] = useState(level === 0);

  if (node.type === "file") {
    return (
      <div
        className="flex items-center gap-2 py-1 px-2 hover:bg-gray-800 cursor-pointer rounded"
        style={{ paddingLeft: `${level * 12 + 8}px` }}
      >
        {node.name.endsWith(".py") ? (
          <FileCode className="w-4 h-4 text-blue-400 flex-shrink-0" />
        ) : (
          <File className="w-4 h-4 text-gray-400 flex-shrink-0" />
        )}
        <span className="text-sm text-gray-300 truncate">{node.name}</span>
      </div>
    );
  }

  return (
    <div>
      <div
        className="flex items-center gap-1 py-1 px-2 hover:bg-gray-800 cursor-pointer rounded"
        style={{ paddingLeft: `${level * 12 + 8}px` }}
        onClick={() => setIsOpen(!isOpen)}
      >
        {isOpen ? (
          <ChevronDown className="w-4 h-4 text-gray-400 flex-shrink-0" />
        ) : (
          <ChevronRight className="w-4 h-4 text-gray-400 flex-shrink-0" />
        )}
        <Folder className="w-4 h-4 text-blue-400 flex-shrink-0" />
        <span className="text-sm text-gray-300 truncate">{node.name}</span>
      </div>
      {isOpen && node.children && (
        <div>
          {node.children.map((child, idx) => (
            <FileTreeNode key={idx} node={child} level={level + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

export function FileExplorer() {
  return (
    <div className="h-full bg-[#161B22] border-r border-gray-800 flex flex-col">
      <div className="h-10 border-b border-gray-800 flex items-center px-3">
        <span className="text-sm font-medium text-gray-300">文件浏览器</span>
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        {fileTree.map((node, idx) => (
          <FileTreeNode key={idx} node={node} />
        ))}
      </div>
    </div>
  );
}
