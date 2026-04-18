import { FileExplorer } from "../components/FileExplorer";
import { CodeEditor } from "../components/CodeEditor";
import { Terminal } from "../components/Terminal";
import { ChatInterface } from "../components/ChatInterface";
import { ThinkingFlow } from "../components/ThinkingFlow";
import { ToolActivity } from "../components/ToolActivity";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";

export function IDEPage() {
  return (
    <div className="h-full w-full">
      <PanelGroup direction="horizontal">
        {/* Left: File Explorer */}
        <Panel defaultSize={15} minSize={10} maxSize={25}>
          <FileExplorer />
        </Panel>

        <PanelResizeHandle className="w-1 bg-gray-800 hover:bg-blue-600 transition-colors" />

        {/* Center: Code Editor + Terminal */}
        <Panel defaultSize={50} minSize={30}>
          <PanelGroup direction="vertical">
            <Panel defaultSize={70} minSize={40}>
              <CodeEditor />
            </Panel>
            <PanelResizeHandle className="h-1 bg-gray-800 hover:bg-blue-600 transition-colors" />
            <Panel defaultSize={30} minSize={20}>
              <Terminal />
            </Panel>
          </PanelGroup>
        </Panel>

        <PanelResizeHandle className="w-1 bg-gray-800 hover:bg-blue-600 transition-colors" />

        {/* Right: Agent Intelligence */}
        <Panel defaultSize={35} minSize={25}>
          <PanelGroup direction="vertical">
            <Panel defaultSize={35} minSize={20}>
              <ChatInterface />
            </Panel>
            <PanelResizeHandle className="h-1 bg-gray-800 hover:bg-blue-600 transition-colors" />
            <Panel defaultSize={35} minSize={20}>
              <ThinkingFlow />
            </Panel>
            <PanelResizeHandle className="h-1 bg-gray-800 hover:bg-blue-600 transition-colors" />
            <Panel defaultSize={30} minSize={20}>
              <ToolActivity />
            </Panel>
          </PanelGroup>
        </Panel>
      </PanelGroup>
    </div>
  );
}
