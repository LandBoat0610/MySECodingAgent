 src/__tests__/api/index.test.js (30)
 ✓ src/__tests__/components/App.test.js (1)
 ✓ src/__tests__/components/ChatPanel.test.js (27)
 ❯ src/__tests__/components/FilePreview.test.js (6)
   ❯ FilePreview.vue (6)
     ✓ should show placeholder when no file selected
     ✓ should display selected file path and type
     ✓ should show loading state
     ✓ should show error state
     ✓ should render file content in pre tag when loaded
     × should return to placeholder when selectedFile is cleared
 ✓ src/__tests__/components/FileTreeNode.test.js (11)
 ✓ src/__tests__/components/FileTreePanel.test.js (5)
 ❯ src/__tests__/components/LiveEvalHud.test.js (11)
   ❯ LiveEvalHud.vue (11)
     ✓ should render panel title
     ✓ should show elapsed time as dash when not started
     × should display token count
     × should display trace step count
     × should display tool call count
     × should display tool success rate when available
     × should display tool avg latency when available
     ✓ should toggle collapse on button click
     × should show elapsed time when agent is running
     × should show ms elapsed when under 1s
     × should expand when agent starts running
 ✓ src/__tests__/components/PlanDialog.test.js (10)
 ✓ src/__tests__/components/ProjectPanel.test.js (20)
 ✓ src/__tests__/layouts/EvalLayout.test.js (8)
 ✓ src/__tests__/layouts/IdeLayout.test.js (5)
 ✓ src/__tests__/stores/agent.test.js (44)
 ✓ src/__tests__/stores/evaluation.test.js (20)
 ✓ src/__tests__/utils/persistence.test.js (8)

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯ Failed Tests 9 ⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯

 FAIL  src/__tests__/components/FilePreview.test.js > FilePreview.vue > should return to placeholder when selectedFile is cleared
AssertionError: expected '/test.js' to be 'File Preview' // Object.is equality

Expected: "File Preview"
Received: "/test.js"

 ❯ src/__tests__/components/FilePreview.test.js:90:55
     88|         await wrapper.vm.$nextTick()
     89| 
     90|         expect(wrapper.find('.preview-title').text()).toBe('File Preview')
       |                                                       ^
     91|         expect(wrapper.find('.preview-badge').exists()).toBe(false)
     92|     })

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[1/9]⎯

 FAIL  src/__tests__/components/LiveEvalHud.test.js > LiveEvalHud.vue > should display token count
AssertionError: expected '实时评测▾本轮耗时NaN sToken（累计）—轨迹步数工具调用 切换工作…' to contain '500'

Expected: "500"
Received: "实时评测▾本轮耗时NaN sToken（累计）—轨迹步数工具调用 切换工作区：请点击预览区左下角附近的「IDE｜评测中心」按钮。指标来自 WebSocket 轨迹与会话快照；首轮 LLM 返回 usage 后 Token 开始递增。"

 ❯ src/__tests__/components/LiveEvalHud.test.js:60:32
     58|         }))
     59|         const wrapper = mount(LiveEvalHud)
     60|         expect(wrapper.text()).toContain('500')
       |                                ^
     61|     })
     62| 

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[2/9]⎯

 FAIL  src/__tests__/components/LiveEvalHud.test.js > LiveEvalHud.vue > should display trace step count
AssertionError: expected '实时评测▾本轮耗时NaN sToken（累计）—轨迹步数工具调用 切换工作…' to contain '3'

Expected: "3"
Received: "实时评测▾本轮耗时NaN sToken（累计）—轨迹步数工具调用 切换工作区：请点击预览区左下角附近的「IDE｜评测中心」按钮。指标来自 WebSocket 轨迹与会话快照；首轮 LLM 返回 usage 后 Token 开始递增。"

 ❯ src/__tests__/components/LiveEvalHud.test.js:68:32
     66|         }))
     67|         const wrapper = mount(LiveEvalHud)
     68|         expect(wrapper.text()).toContain('3')
       |                                ^
     69|     })
     70| 

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[3/9]⎯

 FAIL  src/__tests__/components/LiveEvalHud.test.js > LiveEvalHud.vue > should display tool call count
AssertionError: expected '实时评测▾本轮耗时NaN sToken（累计）—轨迹步数工具调用 切换工作…' to contain '7'

Expected: "7"
Received: "实时评测▾本轮耗时NaN sToken（累计）—轨迹步数工具调用 切换工作区：请点击预览区左下角附近的「IDE｜评测中心」按钮。指标来自 WebSocket 轨迹与会话快照；首轮 LLM 返回 usage 后 Token 开始递增。"

 ❯ src/__tests__/components/LiveEvalHud.test.js:76:32
     74|         }))
     75|         const wrapper = mount(LiveEvalHud)
     76|         expect(wrapper.text()).toContain('7')
       |                                ^
     77|     })
     78| 

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[4/9]⎯

 FAIL  src/__tests__/components/LiveEvalHud.test.js > LiveEvalHud.vue > should display tool success rate when available
AssertionError: expected '实时评测▾本轮耗时NaN sToken（累计）—轨迹步数工具调用 切换工作…' to contain '85%'

Expected: "85%"
Received: "实时评测▾本轮耗时NaN sToken（累计）—轨迹步数工具调用 切换工作区：请点击预览区左下角附近的「IDE｜评测中心」按钮。指标来自 WebSocket 轨迹与会话快照；首轮 LLM 返回 usage 后 Token 开始递增。"

 ❯ src/__tests__/components/LiveEvalHud.test.js:84:32
     82|         }))
     83|         const wrapper = mount(LiveEvalHud)
     84|         expect(wrapper.text()).toContain('85%')
       |                                ^
     85|     })
     86| 

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[5/9]⎯

 FAIL  src/__tests__/components/LiveEvalHud.test.js > LiveEvalHud.vue > should display tool avg latency when available
AssertionError: expected '实时评测▾本轮耗时NaN sToken（累计）—轨迹步数工具调用 切换工作…' to contain '123.4 ms'

Expected: "123.4 ms"
Received: "实时评测▾本轮耗时NaN sToken（累计）—轨迹步数工具调用 切换工作区：请点击预览区左下角附近的「IDE｜评测中心」按钮。指标来自 WebSocket 轨迹与会话快照；首轮 LLM 返回 usage 后 Token 开始递增。"

 ❯ src/__tests__/components/LiveEvalHud.test.js:92:32
     90|         }))
     91|         const wrapper = mount(LiveEvalHud)
     92|         expect(wrapper.text()).toContain('123.4 ms')
       |                                ^
     93|     })
     94| 

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[6/9]⎯

 FAIL  src/__tests__/components/LiveEvalHud.test.js > LiveEvalHud.vue > should show elapsed time when agent is running
AssertionError: expected '实时评测▾本轮耗时NaN sToken（累计）—轨迹步数工具调用 切换工作…' to match /\d+\.\d+\s*s/

- Expected: 
/\d+\.\d+\s*s/

+ Received: 
"实时评测▾本轮耗时NaN sToken（累计）—轨迹步数工具调用 切换工作区：请点击预览区左下角附近的「IDE｜评测中心」按钮。指标来自 WebSocket 轨迹与会话快照；首轮 LLM 返回 usage 后 Token 开始递增。"

 ❯ src/__tests__/components/LiveEvalHud.test.js:120:32
    118|         const wrapper = mount(LiveEvalHud)
    119|         // Should show seconds-based elapsed
    120|         expect(wrapper.text()).toMatch(/\d+\.\d+\s*s/)
       |                                ^
    121|     })
    122| 

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[7/9]⎯

 FAIL  src/__tests__/components/LiveEvalHud.test.js > LiveEvalHud.vue > should show ms elapsed when under 1s
AssertionError: expected '实时评测▾本轮耗时NaN sToken（累计）—轨迹步数工具调用 切换工作…' to match /\d+\s*ms/

- Expected: 
/\d+\s*ms/

+ Received: 
"实时评测▾本轮耗时NaN sToken（累计）—轨迹步数工具调用 切换工作区：请点击预览区左下角附近的「IDE｜评测中心」按钮。指标来自 WebSocket 轨迹与会话快照；首轮 LLM 返回 usage 后 Token 开始递增。"

 ❯ src/__tests__/components/LiveEvalHud.test.js:130:32
    128|         }))
    129|         const wrapper = mount(LiveEvalHud)
    130|         expect(wrapper.text()).toMatch(/\d+\s*ms/)
       |                                ^
    131|     })
    132| 

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[8/9]⎯

 FAIL  src/__tests__/components/LiveEvalHud.test.js > LiveEvalHud.vue > should expand when agent starts running
AssertionError: expected false to be true // Object.is equality

- Expected
+ Received

- true
+ false

 ❯ src/__tests__/components/LiveEvalHud.test.js:149:54
    147|         await wrapper.vm.$nextTick()
    148| 
    149|         expect(wrapper.find('.panel-body').exists()).toBe(true)
       |                                                      ^
    150|     })
    151| })

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[9/9]⎯

 Test Files  2 failed | 12 passed (14)
      Tests  9 failed | 197 passed (206)
   Start at  23:29:28
   Duration  4.81s (transform 1.84s, setup 4.13s, collect 4.31s, tests 1.77s, environment 43.85s, prepare 4.09s)