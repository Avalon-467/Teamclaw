/**
 * Visual Agent Orchestration System - Core Application Logic
 * Handles canvas node management, drag & drop, connections, grouping,
 * and YAML generation.
 */

// ── i18n Internationalization ──
const I18N = {
    zh: {
        // Top bar buttons
        btn_auto_arrange: '🔄 自动排列',
        btn_save: '💾 保存',
        btn_load: '📂 加载',
        btn_llm_prompt: '🤖 LLM 提示词',
        btn_export: '📋 导出 YAML',
        btn_clear: '🗑️ 清空',
        tip_auto_arrange: '自动排列节点为圆形',
        tip_save: '保存当前布局',
        tip_load: '加载已保存的布局',
        tip_llm_prompt: '生成 LLM 提示词用于 YAML 生成',
        tip_export: '复制 YAML 到剪贴板',
        tip_clear: '清空画布',
        tip_copy: '复制',

        // Sidebar
        sidebar_expert_pool: '🧑‍💼 专家池',
        manual_injection: '手动注入',
        manual_inject_desc: '注入固定内容',
        quick_guide_title: '快捷操作：',
        guide_drag: '• 拖入专家到画布',
        guide_connect: '• 连接端口创建工作流',
        guide_group: '• 框选 + Ctrl+G 分组',
        guide_right_click: '• 右键查看更多选项',
        guide_dblclick: '• 双击侧边栏快速添加',

        // Canvas hints
        hint_drag: '拖入专家以开始',
        hint_connect: '连接节点创建工作流<br>分组节点进行并行 / 头脑风暴',

        // Right panel
        panel_settings: '⚙️ 设置',
        setting_repeat: '每轮重复计划',
        setting_max_rounds: '最大轮次：',
        setting_threshold: '聚类阈值：',
        panel_credentials: '🔐 Agent 凭证',
        label_username: '用户名：',
        label_password: '密码：',
        ph_username: '例如 bryankztan',
        ph_password: '密码',
        auth_hint: '🔒 输入凭证以连接 Main Agent',
        panel_yaml_gen: '🤖 Agent YAML 生成器',
        status_idle: '💡 点击"🤖 LLM 提示词"生成 → 发送至 Main Agent → 获取 YAML',
        label_prompt_sent: '📨 发送给 Agent 的提示词',
        label_agent_yaml: '🤖 Agent 生成的 YAML',
        prompt_placeholder: '# 点击"🤖 LLM 提示词"自动生成提示词，\n# 发送至 Main Agent 并获取 YAML。',
        agent_yaml_placeholder: '# Agent 生成的 YAML 将在此显示\n# 点击"🤖 LLM 提示词"后',
        panel_rule_yaml: '📄 规则 YAML',
        yaml_hint: '# 拖入专家到画布以开始构建排程...\n#\n# 空间语义：\n#   → 连接的节点 = 顺序工作流\n#   ○ 分组的节点 = 并行 / 头脑风暴\n#   ★ 所有节点 = all_experts: true\n#   📝 手动节点 = 注入固定内容',

        // Context menu
        ctx_group_parallel: '🔀 设为并行组',
        ctx_group_all: '👥 设为全部专家',
        ctx_chain: '🔗 链接为工作流',
        ctx_delete: '🗑️ 删除选中',
        ctx_add_manual: '📝 添加手动注入',
        ctx_add_custom: '⭐ 添加自定义专家',
        ctx_clear_all: '🧹 清空全部',

        // Modals
        modal_edit_manual: '📝 编辑手动注入',
        modal_add_custom: '⭐ 添加自定义专家',
        modal_author: '作者：',
        modal_content: '内容：',
        modal_name: '名称：',
        modal_tag: '标签：',
        modal_persona: '角色描述：',
        modal_temperature: '温度 (0.0 - 1.0)：',
        modal_cancel: '取消',
        modal_save: '保存',
        modal_add: '添加',
        modal_ph_name: '例如 AI 研究员',
        modal_ph_tag: '例如 ai_researcher',
        modal_ph_persona: '描述该专家的角色和专长...',

        // Toast / status messages
        toast_yaml_copied: 'YAML 已复制到剪贴板！ ✅',
        toast_layout_saved: '布局已保存！ 💾',
        toast_layout_loaded: '布局已加载！ 📂',
        toast_arranged: '节点已排列为圆形！ 🔄',
        toast_chained: '节点已链接为工作流！ 🔗',
        toast_no_nodes: '请先添加节点！ 🎯',
        toast_select_2: '至少选择 2 个节点进行分组',
        toast_select_2_chain: '至少选择 2 个节点进行链接',
        toast_agent_yaml_copied: 'Agent YAML 已复制！ 🤖✅',
        toast_prompt_copied: 'LLM 提示词已复制！ 🤖✅',
        toast_gen_first: '请先生成 YAML！ 🤖',
        toast_prompt_first: '请先生成提示词！ 🤖',
        toast_enter_creds: '请先输入用户名和密码！ 🔑',
        toast_auth_failed: '认证失败 — 检查凭证 🔒',
        toast_agent_unavail: 'Agent 不可用 — 提示词已生成，可手动使用 📋',
        toast_agent_valid: 'Agent 生成了有效的 YAML！ 🤖✅',
        toast_agent_warn: 'Agent 生成了 YAML（有警告） 🤖⚠️',
        toast_save_failed: '保存失败：',
        toast_load_failed: '加载失败：',
        toast_no_layouts: '未找到已保存的布局',
        toast_name_required: '名称为必填项',
        toast_copy_failed: '复制失败',

        // Confirms / prompts
        confirm_clear: '清空所有节点、边和分组？',
        prompt_layout_name: '布局名称：',
        prompt_load_layout: '加载布局：\n\n可用：',

        // Status bar
        status_nodes: '节点',
        status_edges: '边',
        status_groups: '分组',
        status_selected: '选中',

        // Auth / agent status
        auth_missing: '❌ 缺少凭证 — 请填写用户名和密码',
        auth_authenticating: '🔄 正在认证...',
        auth_success: '✅ 已认证为',
        auth_failed: '❌ 认证失败 — 用户名或密码错误',
        auth_conn_issue: '⚠️ Agent 连接问题',
        status_loading: '🔄 正在以 {user} 身份认证并与 Main Agent 通信...',
        status_auth_fail: '🔒 认证失败 — 检查用户名/密码',
        status_agent_unavail: '⚠️ Agent 不可用 — 提示词已生成，可手动使用',
        status_valid_yaml: '✅ 有效 YAML — {steps} 步 [{types}] | repeat: {repeat}',
        status_yaml_warn: '⚠️ YAML 验证问题：{error}',
        status_no_yaml: '❌ Agent 响应中没有 YAML',
        status_conn_error: '❌ 连接错误',
        status_building: '⏳ 正在构建提示词并发送至 Main Agent...',
        status_waiting: '⏳ 等待 Agent 响应...',

        // Group labels
        group_parallel: '🔀 并行',
        group_all: '👥 全部专家',
        group_manual: '📝 手动',
        tip_remove: '删除',
        tip_dissolve: '解散分组',

        // Conditional edge
        ctx_set_conditional: '⚡ 设为条件边',
        ctx_edit_conditional: '✏️ 编辑条件边',
        ctx_remove_conditional: '🔗 恢复为普通边',
        modal_cond_edge: '⚡ 编辑条件边',
        cond_label_condition: '条件表达式',
        cond_label_then: 'Then 目标（条件为真）',
        cond_label_else: 'Else 目标（条件为假/循环回边）',
        cond_hint: '例如: last_post_contains:LGTM, post_count_gte:3, always',
        cond_select_none: '（无）',
        cond_keep_current: '当前目标',
        badge_start: 'START',
        badge_end: 'END',
        btn_remove_cond: '恢复普通边',
    },
    en: {
        btn_auto_arrange: '🔄 Auto Arrange',
        btn_save: '💾 Save',
        btn_load: '📂 Load',
        btn_llm_prompt: '🤖 LLM Prompt',
        btn_export: '📋 Export YAML',
        btn_clear: '🗑️ Clear',
        tip_auto_arrange: 'Auto-arrange nodes in circle',
        tip_save: 'Save current layout',
        tip_load: 'Load saved layout',
        tip_llm_prompt: 'Generate LLM prompt for YAML generation',
        tip_export: 'Copy YAML to clipboard',
        tip_clear: 'Clear canvas',
        tip_copy: 'Copy prompt',

        sidebar_expert_pool: '🧑‍💼 Expert Pool',
        manual_injection: 'Manual Injection',
        manual_inject_desc: 'Inject fixed content',
        quick_guide_title: 'Quick Guide:',
        guide_drag: '• Drag experts to canvas',
        guide_connect: '• Connect ports for workflow',
        guide_group: '• Select + Ctrl+G to group',
        guide_right_click: '• Right-click for more options',
        guide_dblclick: '• Double-click sidebar to add',

        hint_drag: 'Drag experts here to start',
        hint_connect: 'Connect nodes with edges for workflow<br>Group nodes for parallel / brainstorm',

        panel_settings: '⚙️ Settings',
        setting_repeat: 'Repeat plan each round',
        setting_max_rounds: 'Max rounds:',
        setting_threshold: 'Cluster threshold:',
        panel_credentials: '🔐 Agent Credentials',
        label_username: 'Username:',
        label_password: 'Password:',
        ph_username: 'e.g. bryankztan',
        ph_password: 'Password',
        auth_hint: '🔒 Enter credentials to authenticate with Main Agent',
        panel_yaml_gen: '🤖 Agent YAML Generator',
        status_idle: '💡 Click "🤖 LLM Prompt" to generate → send to Main Agent → get YAML',
        label_prompt_sent: '📨 Prompt sent to Agent',
        label_agent_yaml: '🤖 Agent-Generated YAML',
        prompt_placeholder: '# Click "🤖 LLM Prompt" to auto-generate a prompt,\n# send it to the Main Agent, and receive YAML back.',
        agent_yaml_placeholder: '# Agent-generated YAML will appear here\n# after clicking "🤖 LLM Prompt"',
        panel_rule_yaml: '📄 Rule-Based YAML',
        yaml_hint: '# Drag agents to the canvas to start building your schedule...\n#\n# Spatial Semantics:\n#   → Connected nodes = Sequential workflow\n#   ○ Grouped nodes = Parallel / Brainstorm\n#   ★ All nodes = all_experts: true\n#   📝 Manual node = Inject fixed content',

        ctx_group_parallel: '🔀 Group as Parallel',
        ctx_group_all: '👥 Group as All Experts',
        ctx_chain: '🔗 Chain Selected (Workflow)',
        ctx_delete: '🗑️ Delete Selected',
        ctx_add_manual: '📝 Add Manual Injection',
        ctx_add_custom: '⭐ Add Custom Expert',
        ctx_clear_all: '🧹 Clear All',

        modal_edit_manual: '📝 Edit Manual Injection',
        modal_add_custom: '⭐ Add Custom Expert',
        modal_author: 'Author:',
        modal_content: 'Content:',
        modal_name: 'Name:',
        modal_tag: 'Tag:',
        modal_persona: 'Persona:',
        modal_temperature: 'Temperature (0.0 - 1.0):',
        modal_cancel: 'Cancel',
        modal_save: 'Save',
        modal_add: 'Add',
        modal_ph_name: 'e.g. AI Researcher',
        modal_ph_tag: 'e.g. ai_researcher',
        modal_ph_persona: 'Describe this expert\'s role and expertise...',

        toast_yaml_copied: 'YAML copied to clipboard! ✅',
        toast_layout_saved: 'Layout saved! 💾',
        toast_layout_loaded: 'Layout loaded! 📂',
        toast_arranged: 'Nodes arranged in circle! 🔄',
        toast_chained: 'Nodes chained as workflow! 🔗',
        toast_no_nodes: 'Add some nodes first! 🎯',
        toast_select_2: 'Select at least 2 nodes to group',
        toast_select_2_chain: 'Select at least 2 nodes to chain',
        toast_agent_yaml_copied: 'Agent YAML copied! 🤖✅',
        toast_prompt_copied: 'LLM Prompt copied! 🤖✅',
        toast_gen_first: 'Generate YAML from Agent first! 🤖',
        toast_prompt_first: 'Generate a prompt first! 🤖',
        toast_enter_creds: 'Please enter username and password first! 🔑',
        toast_auth_failed: 'Auth failed — check credentials 🔒',
        toast_agent_unavail: 'Agent not available — prompt ready for manual use 📋',
        toast_agent_valid: 'Agent generated valid YAML! 🤖✅',
        toast_agent_warn: 'Agent generated YAML (with warnings) 🤖⚠️',
        toast_save_failed: 'Save failed: ',
        toast_load_failed: 'Load failed: ',
        toast_no_layouts: 'No saved layouts found',
        toast_name_required: 'Name is required',
        toast_copy_failed: 'Copy failed',

        confirm_clear: 'Clear all nodes, edges, and groups?',
        prompt_layout_name: 'Layout name:',
        prompt_load_layout: 'Load layout:\n\nAvailable: ',

        status_nodes: 'Nodes',
        status_edges: 'Edges',
        status_groups: 'Groups',
        status_selected: 'Selected',

        auth_missing: '❌ Missing credentials — please fill in username and password',
        auth_authenticating: '🔄 Authenticating...',
        auth_success: '✅ Authenticated as',
        auth_failed: '❌ Authentication failed — wrong username or password',
        auth_conn_issue: '⚠️ Agent connection issue',
        status_loading: '🔄 Authenticating as {user} and communicating with Main Agent...',
        status_auth_fail: '🔒 Authentication failed — check username/password',
        status_agent_unavail: '⚠️ Agent unavailable — prompt generated for manual use',
        status_valid_yaml: '✅ Valid YAML — {steps} steps [{types}] | repeat: {repeat}',
        status_yaml_warn: '⚠️ YAML validation issue: {error}',
        status_no_yaml: '❌ No YAML in agent response',
        status_conn_error: '❌ Connection error',
        status_building: '⏳ Building prompt and sending to Main Agent...',
        status_waiting: '⏳ Waiting for agent response...',

        group_parallel: '🔀 Parallel',
        group_all: '👥 All Experts',
        group_manual: '📝 Manual',
        tip_remove: 'Remove',
        tip_dissolve: 'Dissolve group',

        // Conditional edge
        ctx_set_conditional: '⚡ Set as Conditional Edge',
        ctx_edit_conditional: '✏️ Edit Conditional Edge',
        ctx_remove_conditional: '🔗 Revert to Fixed Edge',
        modal_cond_edge: '⚡ Edit Conditional Edge',
        cond_label_condition: 'Condition Expression',
        cond_label_then: 'Then Target (condition true)',
        cond_label_else: 'Else Target (condition false / loop back)',
        cond_hint: 'e.g. last_post_contains:LGTM, post_count_gte:3, always',
        cond_select_none: '(none)',
        cond_keep_current: 'Current target',
        badge_start: 'START',
        badge_end: 'END',
        btn_remove_cond: 'Revert to Fixed',
    },
};

let currentLang = localStorage.getItem('visual_lang') || 'en';

/** Get i18n text by key, with optional template params */
function i18n(key, params) {
    const dict = I18N[currentLang] || I18N.en;
    let text = dict[key] || I18N.en[key] || key;
    if (params) {
        Object.keys(params).forEach(k => {
            text = text.replace(new RegExp('\\{' + k + '\\}', 'g'), params[k]);
        });
    }
    return text;
}

/** Apply i18n to all DOM elements with data-i18n attributes */
function applyI18n() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        const text = i18n(key);
        if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
            // skip — use data-i18n-placeholder for these
        } else {
            el.innerHTML = text;
        }
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        el.placeholder = i18n(el.getAttribute('data-i18n-placeholder'));
    });
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
        el.title = i18n(el.getAttribute('data-i18n-title'));
    });
    // Update language button label
    const langBtn = document.getElementById('btn-lang');
    if (langBtn) langBtn.textContent = currentLang === 'zh' ? '🌐 EN' : '🌐 中文';
    // Update status bar
    if (typeof updateStatusBar === 'function') updateStatusBar();
}

/** Toggle language between zh and en */
function toggleLang() {
    currentLang = currentLang === 'zh' ? 'en' : 'zh';
    localStorage.setItem('visual_lang', currentLang);
    applyI18n();
}

// ── Application State ──
const state = {
    experts: [],          // Available expert pool
    nodes: [],            // Canvas nodes: { id, name, tag, emoji, x, y, type, temperature, author, content }
    edges: [],            // Directed edges: { id, source, target, edgeType:'fixed'|'conditional', condition, thenTarget, elseTarget }
    conditionalEdges: [], // Conditional edges derived from edge configs: { source, condition, then, else }
    groups: [],           // Group zones: { id, name, type, x, y, w, h, nodeIds }
    selectedNodes: new Set(),
    nextNodeId: 1,
    nextEdgeId: 1,
    nextGroupId: 1,
    settings: {
        repeat: false,
        max_rounds: 5,
        cluster_threshold: 150,
    },
    // Interaction state
    dragging: null,       // { nodeId, offsetX, offsetY } | { type: 'canvas', startX, startY }
    connecting: null,     // { sourceId, startX, startY }
    selecting: null,      // { startX, startY }
    contextMenu: null,
    panOffset: { x: 0, y: 0 },
};

// ── Initialization ──
document.addEventListener('DOMContentLoaded', async () => {
    await loadExperts();
    renderSidebar();
    setupCanvasEvents();
    setupTopBarEvents();
    setupSettingsEvents();
    updateYamlOutput();
    applyI18n();
});

async function loadExperts() {
    try {
        const resp = await fetch('/api/experts');
        state.experts = await resp.json();
    } catch (e) {
        console.error('Failed to load experts:', e);
    }
}

// ── Sidebar Rendering ──
function renderSidebar() {
    const list = document.getElementById('expert-list');
    list.innerHTML = '';

    state.experts.forEach(expert => {
        const card = document.createElement('div');
        card.className = 'expert-card';
        card.draggable = true;
        card.dataset.tag = expert.tag;
        card.innerHTML = `
            <span class="emoji">${expert.emoji}</span>
            <div class="info">
                <div class="name">${expert.name}</div>
                <div class="tag">${expert.tag}</div>
            </div>
            <span class="temp">${expert.temperature}</span>
        `;
        card.addEventListener('dragstart', (e) => {
            e.dataTransfer.setData('application/json', JSON.stringify({
                type: 'expert',
                ...expert
            }));
            e.dataTransfer.effectAllowed = 'copy';
        });
        // Double-click to quick-add to canvas center
        card.addEventListener('dblclick', () => {
            addNodeToCenter({ type: 'expert', ...expert });
        });
        list.appendChild(card);
    });
}

// ── Canvas Node Management ──
function addNodeToCanvas(data, x, y) {
    const id = 'n' + state.nextNodeId++;
    const node = {
        id,
        name: data.name,
        tag: data.tag || 'custom',
        emoji: data.emoji || '⭐',
        x: Math.round(x),
        y: Math.round(y),
        type: data.type || 'expert',
        temperature: data.temperature || 0.5,
        author: data.author || '主持人',
        content: data.content || '',
        stateful: data.stateful || false,
    };
    state.nodes.push(node);
    renderNode(node);
    updateYamlOutput();
    updateStatusBar();
    return node;
}

/**
 * Add a node to the center of the canvas with smart offset to avoid overlapping.
 * Nodes are placed in a spiral pattern around the center.
 */
function addNodeToCenter(data) {
    const area = document.getElementById('canvas-area');
    const areaW = area.offsetWidth;
    const areaH = area.offsetHeight;
    const centerX = areaW / 2 - 60;
    const centerY = areaH / 2 - 20;

    // Smart offset: spiral outward based on existing node count
    const existingCount = state.nodes.length;
    const spiralStep = 80; // pixels between spiral rings
    const angleStep = 137.5 * (Math.PI / 180); // golden angle for nice distribution
    const angle = existingCount * angleStep;
    const radius = spiralStep * Math.sqrt(existingCount) * 0.5;

    const x = centerX + radius * Math.cos(angle);
    const y = centerY + radius * Math.sin(angle);

    return addNodeToCanvas(data, x, y);
}

function renderNode(node) {
    const area = document.getElementById('canvas-area');
    const el = document.createElement('div');
    el.className = 'canvas-node'
        + (node.type === 'manual' ? ' manual-node' : '')
        + (node.type === 'external' ? ' external-node' : '');
    el.id = 'node-' + node.id;
    el.style.left = node.x + 'px';
    el.style.top = node.y + 'px';

    let tagLabel = node.tag;
    if (node.type === 'external') {
        tagLabel = `${node.tag} 🌐 ${node.api_url || 'ext'}`;
        if (node.headers && typeof node.headers === 'object') {
            const hdrParts = Object.entries(node.headers).map(([k, v]) => `${k}: ${v}`);
            if (hdrParts.length) {
                tagLabel += `\n${hdrParts.join('\n')}`;
            }
        }
    }
    const statefulBadge = (node.stateful && node.type !== 'external') ? ' <span style="display:inline-block;background:#8b5cf6;color:#fff;font-size:8px;font-weight:600;border-radius:3px;padding:0 3px;margin-left:3px;vertical-align:middle;" title="Stateful">⚡S</span>' : '';

    el.innerHTML = `
        <span class="node-emoji">${node.emoji}</span>
        <div class="node-info">
            <div class="node-name">${node.name}${statefulBadge}</div>
            <div class="node-tag">${tagLabel}</div>
        </div>
        <div class="node-delete" title="${i18n ? i18n('tip_remove') : 'Remove'}">×</div>
        <div class="port port-in" data-node="${node.id}" data-dir="in"></div>
        <div class="port port-out" data-node="${node.id}" data-dir="out"></div>
    `;

    // Delete button
    el.querySelector('.node-delete').addEventListener('click', (e) => {
        e.stopPropagation();
        removeNode(node.id);
    });

    // Node drag
    el.addEventListener('mousedown', (e) => {
        if (e.target.classList.contains('port')) return;
        if (e.target.classList.contains('node-delete')) return;
        e.stopPropagation();

        // Select logic
        if (!e.shiftKey && !state.selectedNodes.has(node.id)) {
            clearSelection();
        }
        selectNode(node.id);

        state.dragging = {
            nodeId: node.id,
            offsetX: e.clientX - node.x,
            offsetY: e.clientY - node.y,
            multiDrag: state.selectedNodes.size > 1,
            startPositions: {},
        };

        // Store start positions for multi-drag
        if (state.selectedNodes.size > 1) {
            state.selectedNodes.forEach(nid => {
                const n = state.nodes.find(nn => nn.id === nid);
                if (n) state.dragging.startPositions[nid] = { x: n.x, y: n.y };
            });
        }
    });

    // Connection ports
    el.querySelectorAll('.port').forEach(port => {
        port.addEventListener('mousedown', (e) => {
            e.stopPropagation();
            if (port.dataset.dir === 'out') {
                const rect = port.getBoundingClientRect();
                const canvasRect = document.getElementById('canvas-area').getBoundingClientRect();
                state.connecting = {
                    sourceId: node.id,
                    startX: rect.left + 6 - canvasRect.left,
                    startY: rect.top + 6 - canvasRect.top,
                };
            }
        });

        port.addEventListener('mouseup', (e) => {
            e.stopPropagation();
            if (state.connecting && port.dataset.dir === 'in' && port.dataset.node !== state.connecting.sourceId) {
                addEdge(state.connecting.sourceId, node.id);
            }
            state.connecting = null;
            removeTempLine();
        });
    });

    // Double-click to edit (for manual nodes)
    el.addEventListener('dblclick', () => {
        if (node.type === 'manual') {
            showManualEditModal(node);
        }
    });

    area.appendChild(el);
}

function removeNode(nodeId) {
    state.nodes = state.nodes.filter(n => n.id !== nodeId);
    state.edges = state.edges.filter(e => e.source !== nodeId && e.target !== nodeId);
    state.selectedNodes.delete(nodeId);

    // Remove from groups
    state.groups.forEach(g => {
        g.nodeIds = g.nodeIds.filter(id => id !== nodeId);
    });

    const el = document.getElementById('node-' + nodeId);
    if (el) el.remove();

    renderAllEdges();
    updateNodeBadges();
    updateYamlOutput();
    updateStatusBar();
}

function selectNode(nodeId) {
    state.selectedNodes.add(nodeId);
    const el = document.getElementById('node-' + nodeId);
    if (el) el.classList.add('selected');
}

function clearSelection() {
    state.selectedNodes.forEach(nid => {
        const el = document.getElementById('node-' + nid);
        if (el) el.classList.remove('selected');
    });
    state.selectedNodes.clear();
}

// ── Edge Management ──
function addEdge(sourceId, targetId, edgeType = 'fixed') {
    // Prevent duplicate
    if (state.edges.some(e => e.source === sourceId && e.target === targetId)) return;
    const id = 'e' + state.nextEdgeId++;
    state.edges.push({ id, source: sourceId, target: targetId, edgeType, condition: '', thenTarget: '', elseTarget: '' });
    renderAllEdges();
    updateNodeBadges();
    updateYamlOutput();
}

function removeEdge(edgeId) {
    state.edges = state.edges.filter(e => e.id !== edgeId);
    renderAllEdges();
    updateNodeBadges();
    updateYamlOutput();
}

function renderAllEdges() {
    const svg = document.getElementById('edge-svg');
    // Keep only the defs and temp-line
    const defs = svg.querySelector('defs');
    svg.innerHTML = '';
    if (defs) svg.appendChild(defs);
    else {
        const newDefs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
        newDefs.innerHTML = `
            <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
                <polygon points="0 0, 10 3.5, 0 7" fill="#667eea" />
            </marker>
            <marker id="arrowhead-green" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
                <polygon points="0 0, 10 3.5, 0 7" fill="#44bb88" />
            </marker>
            <marker id="arrowhead-orange" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
                <polygon points="0 0, 10 3.5, 0 7" fill="#ff8844" />
            </marker>
        `;
        svg.appendChild(newDefs);
    }

    state.edges.forEach(edge => {
        const srcNode = state.nodes.find(n => n.id === edge.source);
        const tgtNode = state.nodes.find(n => n.id === edge.target);
        if (!srcNode || !tgtNode) return;

        const srcEl = document.getElementById('node-' + edge.source);
        const tgtEl = document.getElementById('node-' + edge.target);
        if (!srcEl || !tgtEl) return;

        const x1 = srcNode.x + srcEl.offsetWidth;
        const y1 = srcNode.y + srcEl.offsetHeight / 2;
        const x2 = tgtNode.x;
        const y2 = tgtNode.y + tgtEl.offsetHeight / 2;

        const isConditional = edge.edgeType === 'conditional';
        // Detect back-edge: target is to the left of source (loop)
        const isBackEdge = tgtNode.x + (tgtEl.offsetWidth / 2) < srcNode.x + (srcEl.offsetWidth / 2);

        let pathD;
        if (isBackEdge) {
            // Draw arc below/above the nodes for back-edges
            const arcY = Math.max(srcNode.y + srcEl.offsetHeight, tgtNode.y + tgtEl.offsetHeight) + 60;
            const bx1 = srcNode.x + srcEl.offsetWidth / 2;
            const by1 = srcNode.y + srcEl.offsetHeight;
            const bx2 = tgtNode.x + tgtEl.offsetWidth / 2;
            const by2 = tgtNode.y + tgtEl.offsetHeight;
            pathD = `M${bx1},${by1} C${bx1},${arcY} ${bx2},${arcY} ${bx2},${by2}`;
        } else {
            // Normal bezier curve
            const cpx = (x1 + x2) / 2;
            pathD = `M${x1},${y1} C${cpx},${y1} ${cpx},${y2} ${x2},${y2}`;
        }

        // Determine style based on edge type
        let strokeColor, markerEnd, dashArray;
        if (isConditional && isBackEdge) {
            // else / loop-back edge: orange dashed
            strokeColor = '#ff8844';
            markerEnd = 'url(#arrowhead-orange)';
            dashArray = '6,4';
        } else if (isConditional) {
            // then edge: green solid
            strokeColor = '#44bb88';
            markerEnd = 'url(#arrowhead-green)';
            dashArray = null;
        } else {
            // fixed edge: blue solid
            strokeColor = '#667eea';
            markerEnd = 'url(#arrowhead)';
            dashArray = null;
        }

        const line = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        line.setAttribute('d', pathD);
        line.setAttribute('stroke', strokeColor);
        line.setAttribute('stroke-width', '2');
        line.setAttribute('fill', 'none');
        line.setAttribute('marker-end', markerEnd);
        if (dashArray) line.setAttribute('stroke-dasharray', dashArray);
        line.setAttribute('data-edge-id', edge.id);
        line.style.cursor = 'pointer';
        line.style.pointerEvents = 'all';

        // Store original color for hover restore
        const origColor = strokeColor;

        // Left-click to delete edge, right-click to edit conditional
        line.addEventListener('click', (e) => {
            e.stopPropagation();
            removeEdge(edge.id);
        });

        // Right-click for conditional edge editing
        line.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            e.stopPropagation();
            showEdgeContextMenu(e.clientX, e.clientY, edge);
        });

        // Hover effect
        line.addEventListener('mouseenter', () => { line.setAttribute('stroke', '#ff6b6b'); line.setAttribute('stroke-width', '3'); });
        line.addEventListener('mouseleave', () => { line.setAttribute('stroke', origColor); line.setAttribute('stroke-width', '2'); });

        svg.appendChild(line);

        // Draw label for conditional edges
        if (isConditional && edge.condition) {
            const labelText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            // Position label at midpoint of the path
            let labelX, labelY;
            if (isBackEdge) {
                const bx1 = srcNode.x + srcEl.offsetWidth / 2;
                const bx2 = tgtNode.x + tgtEl.offsetWidth / 2;
                const arcY = Math.max(srcNode.y + srcEl.offsetHeight, tgtNode.y + tgtEl.offsetHeight) + 60;
                labelX = (bx1 + bx2) / 2;
                labelY = arcY + 14;
            } else {
                labelX = (x1 + x2) / 2;
                labelY = (y1 + y2) / 2 - 8;
            }
            labelText.setAttribute('x', labelX);
            labelText.setAttribute('y', labelY);
            labelText.setAttribute('text-anchor', 'middle');
            labelText.classList.add('edge-label');
            labelText.classList.add(isBackEdge ? 'else-label' : 'then-label');
            const displayCond = edge.condition.length > 25 ? edge.condition.slice(0, 22) + '...' : edge.condition;
            labelText.textContent = (isBackEdge ? '❌ ' : '✅ ') + displayCond;
            svg.appendChild(labelText);
        }
    });
}

/** Show context menu on right-clicking an edge */
function showEdgeContextMenu(x, y, edge) {
    hideContextMenu();
    const menu = document.createElement('div');
    menu.className = 'context-menu';
    menu.style.left = x + 'px';
    menu.style.top = y + 'px';

    const items = [];
    if (edge.edgeType === 'conditional') {
        items.push({ icon: '✏️', label: i18n('ctx_edit_conditional'), action: () => showCondEdgeModal(edge) });
        items.push({ icon: '🔗', label: i18n('ctx_remove_conditional'), action: () => {
            edge.edgeType = 'fixed';
            edge.condition = '';
            edge.thenTarget = '';
            // Remove the else edge if exists
            if (edge.elseTarget) {
                state.edges = state.edges.filter(e => !(e.source === edge.source && e.target === edge.elseTarget && e._isElseSibling === edge.id));
                edge.elseTarget = '';
            }
            renderAllEdges();
            updateNodeBadges();
            updateYamlOutput();
        }});
    } else {
        items.push({ icon: '⚡', label: i18n('ctx_set_conditional'), action: () => showCondEdgeModal(edge) });
    }
    items.push({ divider: true });
    items.push({ icon: '🗑️', label: i18n('ctx_delete'), action: () => removeEdge(edge.id) });

    items.forEach(item => {
        if (item.divider) {
            const d = document.createElement('div');
            d.className = 'divider';
            menu.appendChild(d);
        } else {
            const mi = document.createElement('div');
            mi.className = 'menu-item';
            mi.innerHTML = `<span>${item.icon}</span> ${item.label}`;
            mi.addEventListener('click', () => { hideContextMenu(); item.action(); });
            menu.appendChild(mi);
        }
    });

    document.body.appendChild(menu);
    state.contextMenu = menu;
    setTimeout(() => {
        document.addEventListener('click', hideContextMenu, { once: true });
    }, 10);
}

/** Show modal to edit conditional edge properties */
function showCondEdgeModal(edge) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';

    // Build node options for then/else targets
    const otherNodes = state.nodes.filter(n => n.id !== edge.source);
    const nodeOptions = otherNodes.map(n => `<option value="${n.id}">${n.emoji} ${n.name} (${n.id})</option>`).join('');
    const noneOption = `<option value="">${i18n('cond_select_none')}</option>`;

    // Current then target = edge.target (the edge's current target)
    const currentThenId = edge.target;
    const currentElseId = edge.elseTarget || '';

    overlay.innerHTML = `
        <div class="cond-edge-modal">
            <h3>${i18n('modal_cond_edge')}</h3>
            <div class="field-group">
                <label>${i18n('cond_label_condition')}</label>
                <input type="text" id="cond-expr" value="${edge.condition || ''}" placeholder="last_post_contains:LGTM">
                <div class="hint">${i18n('cond_hint')}</div>
            </div>
            <div class="field-group">
                <label>${i18n('cond_label_then')}</label>
                <select id="cond-then">
                    ${nodeOptions}
                </select>
            </div>
            <div class="field-group">
                <label>${i18n('cond_label_else')}</label>
                <select id="cond-else">
                    ${noneOption}
                    ${nodeOptions}
                </select>
            </div>
            <div class="modal-buttons">
                <button id="cond-cancel">${i18n('modal_cancel')}</button>
                ${edge.edgeType === 'conditional' ? `<button id="cond-remove" class="danger">${i18n('btn_remove_cond')}</button>` : ''}
                <button id="cond-save" class="primary">${i18n('modal_save')}</button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);

    // Set current values
    const thenSelect = overlay.querySelector('#cond-then');
    const elseSelect = overlay.querySelector('#cond-else');
    thenSelect.value = currentThenId;
    elseSelect.value = currentElseId;

    overlay.querySelector('#cond-cancel').addEventListener('click', () => overlay.remove());
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });

    const removeBtn = overlay.querySelector('#cond-remove');
    if (removeBtn) {
        removeBtn.addEventListener('click', () => {
            edge.edgeType = 'fixed';
            edge.condition = '';
            edge.thenTarget = '';
            // Remove else sibling edge
            if (edge.elseTarget) {
                state.edges = state.edges.filter(e => !(e.source === edge.source && e.target === edge.elseTarget && e._isElseSibling === edge.id));
                edge.elseTarget = '';
            }
            overlay.remove();
            renderAllEdges();
            updateNodeBadges();
            updateYamlOutput();
        });
    }

    overlay.querySelector('#cond-save').addEventListener('click', () => {
        const condition = document.getElementById('cond-expr').value.trim();
        const thenTarget = thenSelect.value;
        const elseTarget = elseSelect.value;

        if (!condition) {
            showToast('Condition is required');
            return;
        }

        // Update main edge to be conditional
        edge.edgeType = 'conditional';
        edge.condition = condition;
        edge.target = thenTarget;
        edge.thenTarget = thenTarget;

        // Handle else target: remove old else-sibling edge if any
        state.edges = state.edges.filter(e => !e._isElseSibling || e._isElseSibling !== edge.id);

        if (elseTarget) {
            edge.elseTarget = elseTarget;
            // Create a sibling edge for the else branch (visual only, rendered as back-edge style)
            const elseEdgeId = 'e' + state.nextEdgeId++;
            state.edges.push({
                id: elseEdgeId,
                source: edge.source,
                target: elseTarget,
                edgeType: 'conditional',
                condition: edge.condition,
                thenTarget: '',
                elseTarget: '',
                _isElseSibling: edge.id,  // Mark as generated from parent conditional
            });
        } else {
            edge.elseTarget = '';
        }

        overlay.remove();
        renderAllEdges();
        updateNodeBadges();
        updateYamlOutput();
    });
}

/** Update START/END badges on nodes based on edge topology */
function updateNodeBadges() {
    // Remove all existing badges
    document.querySelectorAll('.node-badge').forEach(b => b.remove());

    if (state.nodes.length === 0) return;

    // Compute in-degree and out-degree (only count non-else-sibling edges)
    const realEdges = state.edges.filter(e => !e._isElseSibling);
    const inDeg = {};
    const outDeg = {};
    state.nodes.forEach(n => { inDeg[n.id] = 0; outDeg[n.id] = 0; });
    realEdges.forEach(e => {
        if (inDeg.hasOwnProperty(e.target)) inDeg[e.target]++;
        if (outDeg.hasOwnProperty(e.source)) outDeg[e.source]++;
    });

    // Only show badges if there are edges (otherwise it's just floating nodes)
    if (realEdges.length === 0) return;

    state.nodes.forEach(n => {
        const el = document.getElementById('node-' + n.id);
        if (!el) return;

        // START badge: no incoming edges
        if (inDeg[n.id] === 0) {
            const badge = document.createElement('div');
            badge.className = 'node-badge start-badge';
            badge.textContent = '▶ ' + i18n('badge_start');
            el.appendChild(badge);
        }

        // END badge: no outgoing edges
        if (outDeg[n.id] === 0) {
            const badge = document.createElement('div');
            badge.className = 'node-badge end-badge';
            badge.textContent = '■ ' + i18n('badge_end');
            el.appendChild(badge);
        }
    });
}

function removeTempLine() {
    const svg = document.getElementById('edge-svg');
    const temp = svg.querySelector('.temp-line');
    if (temp) temp.remove();
}

function drawTempLine(x1, y1, x2, y2) {
    const svg = document.getElementById('edge-svg');
    removeTempLine();
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    line.classList.add('temp-line');
    line.setAttribute('x1', x1);
    line.setAttribute('y1', y1);
    line.setAttribute('x2', x2);
    line.setAttribute('y2', y2);
    line.setAttribute('stroke', '#667eea80');
    line.setAttribute('stroke-width', '2');
    line.setAttribute('stroke-dasharray', '5,5');
    svg.appendChild(line);
}

// ── Group Management ──
function createGroup(type, x, y, w, h, nodeIds) {
    const id = 'g' + state.nextGroupId++;
    const labelMap = { parallel: i18n('group_parallel'), all: i18n('group_all'), manual: i18n('group_manual') };
    const group = {
        id,
        name: labelMap[type] || type,
        type,
        x, y, w, h,
        nodeIds: [...nodeIds],
    };
    state.groups.push(group);
    renderGroup(group);
    updateYamlOutput();
    return group;
}

function renderGroup(group) {
    const area = document.getElementById('canvas-area');
    const el = document.createElement('div');
    el.className = 'group-zone ' + group.type;
    el.id = 'group-' + group.id;
    el.style.left = group.x + 'px';
    el.style.top = group.y + 'px';
    el.style.width = group.w + 'px';
    el.style.height = group.h + 'px';

    el.innerHTML = `
        <span class="group-label">${group.name}</span>
        <div class="group-delete" title="${i18n ? i18n('tip_dissolve') : 'Dissolve group'}">×</div>
    `;

    el.querySelector('.group-delete').addEventListener('click', (e) => {
        e.stopPropagation();
        removeGroup(group.id);
    });

    area.appendChild(el);
}

function removeGroup(groupId) {
    state.groups = state.groups.filter(g => g.id !== groupId);
    const el = document.getElementById('group-' + groupId);
    if (el) el.remove();
    updateYamlOutput();
}

function updateGroupBounds(group) {
    // Recalculate group bounds from member nodes
    const members = state.nodes.filter(n => group.nodeIds.includes(n.id));
    if (members.length === 0) return;

    const padding = 30;
    const minX = Math.min(...members.map(n => n.x)) - padding;
    const minY = Math.min(...members.map(n => n.y)) - padding;
    const maxX = Math.max(...members.map(n => {
        const el = document.getElementById('node-' + n.id);
        return n.x + (el ? el.offsetWidth : 120);
    })) + padding;
    const maxY = Math.max(...members.map(n => {
        const el = document.getElementById('node-' + n.id);
        return n.y + (el ? el.offsetHeight : 50);
    })) + padding;

    group.x = minX;
    group.y = minY;
    group.w = maxX - minX;
    group.h = maxY - minY;

    const el = document.getElementById('group-' + group.id);
    if (el) {
        el.style.left = group.x + 'px';
        el.style.top = group.y + 'px';
        el.style.width = group.w + 'px';
        el.style.height = group.h + 'px';
    }
}
