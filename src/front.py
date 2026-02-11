from flask import Flask, render_template_string, request, jsonify
import requests

app = Flask(__name__)

# --- 配置区 ---
# 指向你本地正在运行的 FastAPI Agent 端口
LOCAL_AGENT_URL = "http://127.0.0.1:8000/ask"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>Xavier AnyControl | AI Agent</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/marked/9.1.2/marked.min.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/styles/github-dark.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/highlight.min.js"></script>

    <style>
        .chat-container { height: calc(100vh - 180px); }
        .markdown-body pre { background: #1e1e1e; padding: 1rem; border-radius: 0.5rem; margin: 0.5rem 0; overflow-x: auto; }
        .markdown-body code { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 0.9em; }
        .message-user { border-radius: 1.25rem 1.25rem 0.2rem 1.25rem; }
        .message-agent { border-radius: 1.25rem 1.25rem 1.25rem 0.2rem; }
        .dot { width: 6px; height: 6px; background: #3b82f6; border-radius: 50%; animation: pulse 1.5s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 0.3; transform: scale(0.8); } 50% { opacity: 1; transform: scale(1.2); } }
    </style>
</head>
<body class="bg-gray-100 font-sans leading-normal tracking-normal">

    <!-- ========== 登录页 ========== -->
    <div id="login-screen" class="min-h-screen flex items-center justify-center">
        <div class="bg-white rounded-2xl shadow-2xl p-8 w-full max-w-md border">
            <div class="flex items-center justify-center space-x-3 mb-6">
                <div class="bg-blue-600 p-3 rounded-xl text-white font-bold text-2xl">X</div>
                <h1 class="text-2xl font-bold text-gray-800">Xavier AnyControl</h1>
            </div>
            <p class="text-center text-gray-500 text-sm mb-8">输入用户名以开始对话</p>
            <div class="space-y-4">
                <input id="username-input" type="text" maxlength="32"
                    class="w-full p-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 text-center text-lg"
                    placeholder="请输入用户名" autofocus>
                <button onclick="handleLogin()" id="login-btn"
                    class="w-full bg-blue-600 hover:bg-blue-700 text-white py-3 rounded-xl font-bold text-lg transition-all shadow-lg">
                    进入
                </button>
            </div>
            <p class="text-xs text-gray-400 text-center mt-6">用户名将作为身份标识，用于隔离对话和文件</p>
        </div>
    </div>

    <!-- ========== 聊天页（初始隐藏） ========== -->
    <div id="chat-screen" class="max-w-4xl mx-auto h-screen flex-col shadow-2xl bg-white border-x border-gray-200" style="display:none;">
        <header class="p-4 border-b bg-white flex justify-between items-center sticky top-0 z-10">
            <div class="flex items-center space-x-3">
                <div class="bg-blue-600 p-2 rounded-lg text-white font-bold text-xl">X</div>
                <div>
                    <h1 class="text-lg font-bold text-gray-800 leading-tight">Xavier AnyControl</h1>
                    <p class="text-xs text-green-500 flex items-center">● 链路已加密 (HTTPS)</p>
                </div>
            </div>
            <div class="flex items-center space-x-2">
                <div id="uid-display" class="text-sm font-mono bg-gray-100 px-3 py-1 rounded border"></div>
                <button onclick="handleLogout()" class="text-xs text-gray-400 hover:text-red-500 px-2 py-1 rounded transition-colors" title="切换用户">退出</button>
            </div>
        </header>

        <div id="chat-box" class="chat-container overflow-y-auto p-6 space-y-6 flex-grow bg-gray-50">
            <div class="flex justify-start">
                <div class="message-agent bg-white border p-4 max-w-[85%] shadow-sm text-gray-700">
                    你好！我是 Xavier 智能助手。我已经准备好为你服务，请输入你的指令。
                </div>
            </div>
        </div>

        <div class="p-4 border-t bg-white">
            <div class="flex items-end space-x-3">
                <div class="flex-grow">
                    <textarea id="user-input" rows="1" 
                        class="w-full p-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none transition-all"
                        placeholder="输入指令，Shift + Enter 换行..."></textarea>
                </div>
                <button onclick="handleSend()" id="send-btn"
                    class="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-xl transition-all font-bold shadow-lg h-[50px]">
                    发送
                </button>
            </div>
            <p class="text-[10px] text-center text-gray-400 mt-3 font-mono">Secured by Nginx Reverse Proxy & SSH Tunnel</p>
        </div>
    </div>

    <script>
        marked.setOptions({
            highlight: function(code, lang) {
                const language = hljs.getLanguage(lang) ? lang : 'plaintext';
                return hljs.highlight(code, { language }).value;
            },
            langPrefix: 'hljs language-'
        });

        let currentUserId = null;

        // ===== 登录逻辑 =====
        function handleLogin() {
            const input = document.getElementById('username-input');
            const name = input.value.trim();
            if (!name) { input.focus(); return; }

            // 仅允许字母、数字、下划线、短横线
            if (!/^[a-zA-Z0-9_\\-\\u4e00-\\u9fa5]+$/.test(name)) {
                alert('用户名只能包含字母、数字、下划线、短横线或中文');
                return;
            }

            currentUserId = name;
            localStorage.setItem('userId', name);

            document.getElementById('uid-display').textContent = 'UID: ' + name;
            document.getElementById('login-screen').style.display = 'none';
            document.getElementById('chat-screen').style.display = 'flex';
            document.getElementById('user-input').focus();
        }

        function handleLogout() {
            currentUserId = null;
            localStorage.removeItem('userId');
            document.getElementById('chat-screen').style.display = 'none';
            document.getElementById('login-screen').style.display = 'flex';
            document.getElementById('username-input').value = '';
            document.getElementById('username-input').focus();
            // 清空聊天记录（UI 层面）
            const chatBox = document.getElementById('chat-box');
            chatBox.innerHTML = `
                <div class="flex justify-start">
                    <div class="message-agent bg-white border p-4 max-w-[85%] shadow-sm text-gray-700">
                        你好！我是 Xavier 智能助手。我已经准备好为你服务，请输入你的指令。
                    </div>
                </div>`;
        }

        // 页面加载时自动恢复登录状态
        (function autoLogin() {
            const saved = localStorage.getItem('userId');
            if (saved) {
                document.getElementById('username-input').value = saved;
                handleLogin();
            }
        })();

        // 登录输入框回车
        document.getElementById('username-input').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') { e.preventDefault(); handleLogin(); }
        });

        // ===== 聊天逻辑 =====
        const chatBox = document.getElementById('chat-box');
        const inputField = document.getElementById('user-input');
        const sendBtn = document.getElementById('send-btn');

        function appendMessage(content, isUser = false) {
            const wrapper = document.createElement('div');
            wrapper.className = `flex ${isUser ? 'justify-end' : 'justify-start'} animate-in fade-in duration-300`;
            const div = document.createElement('div');
            div.className = `p-4 max-w-[85%] shadow-sm ${isUser ? 'bg-blue-600 text-white message-user' : 'bg-white border text-gray-800 message-agent'}`;
            if (isUser) {
                div.innerText = content;
            } else {
                div.className += " markdown-body";
                div.innerHTML = marked.parse(content);
                div.querySelectorAll('pre code').forEach((block) => hljs.highlightElement(block));
            }
            wrapper.appendChild(div);
            chatBox.appendChild(wrapper);
            chatBox.scrollTop = chatBox.scrollHeight;
            return div;
        }

        function showTyping() {
            const wrapper = document.createElement('div');
            wrapper.id = 'typing-indicator';
            wrapper.className = 'flex justify-start';
            wrapper.innerHTML = `
                <div class="message-agent bg-white border p-4 flex space-x-2 items-center shadow-sm">
                    <div class="dot"></div><div class="dot"></div><div class="dot"></div>
                </div>`;
            chatBox.appendChild(wrapper);
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        async function handleSend() {
            const text = inputField.value.trim();
            if (!text || sendBtn.disabled) return;

            appendMessage(text, true);
            inputField.value = '';
            inputField.style.height = 'auto';
            sendBtn.disabled = true;
            showTyping();

            try {
                const response = await fetch("/proxy_ask", {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content: text, user_id: currentUserId })
                });
                const typingIndicator = document.getElementById('typing-indicator');
                if (typingIndicator) typingIndicator.remove();
                if (!response.ok) throw new Error("Agent 响应异常");
                const data = await response.json();
                const agentReply = data.response || data.output || JSON.stringify(data);
                appendMessage(agentReply, false);
            } catch (error) {
                const typingIndicator = document.getElementById('typing-indicator');
                if (typingIndicator) typingIndicator.remove();
                appendMessage("❌ 错误: " + error.message, false);
            } finally {
                sendBtn.disabled = false;
            }
        }

        inputField.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = (this.scrollHeight) + 'px';
        });
        inputField.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
        });
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/proxy_ask", methods=["POST"])
def proxy_ask():
    user_content = request.json.get("content")
    user_id = request.json.get("user_id", "anonymous")
    
    payload = {
        "user_id": user_id,
        "text": user_content
    }
    
    try:
        # Flask 作为中转，直接调本机 8000 端口
        r = requests.post(LOCAL_AGENT_URL, json=payload, timeout=120)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # 重要：运行在 9000 端口，对应你的隧道设置
    app.run(host="127.0.0.1", port=9000, debug=False)