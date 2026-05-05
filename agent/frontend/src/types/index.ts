// API 类型定义

export interface Project {
  id: string
  name: string
  workspace_path: string
  created_at: string
  description: string
}

export interface Session {
  id: string
  project_id: string
  title: string
  created_at: string
  status: string
}

export interface Plan {
  id: string
  session_id: string
  content: string
  status: string
  created_at: string
}

export interface AgentState {
  session_id: string
  project_id: string
  task: string
  messages: Array<{role: string; content: string}>
  workspace_dir: string
  project_root: string
  status: string
  task_list: string[]
  current_task_index: number
  current_task: string
  code_context: string
  target_file: string
  run_command: string
  last_tool_result: Record<string, any>
  last_execution: Record<string, any>
  errors: Array<Record<string, any>>
  reflections: number
  trace: Array<Record<string, any>>
  used_tools: string[]
  result_history: string[]
  modified_files: string[]
  final_answer: string
  original_target_path: string
  should_sync_back: boolean
}

export interface FileTreeNode {
  path: string
  type: 'file' | 'directory'
  children: FileTreeNode[] | null
}

export interface ChatRequest {
  message: string
}

export interface ChatResponse {
  session_id: string
  reply: string
  status: string
}

export interface PlanActionRequest {
  action: 'agree' | 'refine' | 'skip' | 'stop'
}

export interface PlanActionResponse {
  plan_id: string
  action: string
  status: string
}

export interface WebSocketMessage {
  type?: string
  phase?: string
  message?: string
  data?: {
    time: string
    phase: string
    content: string
    meta: Record<string, any>
  }
  final_answer?: string
  status?: string
  error?: string
}