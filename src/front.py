from flask import Flask, render_template_string, request, jsonify, session, Response
import requests
import os
from dotenv import load_dotenv

# 加载 .env 配置
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
load_dotenv(dotenv_path=os.path.join(root_dir, "config", ".env"))

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB for image uploads

# --- 配置区 ---
PORT_AGENT = int(os.getenv("PORT_AGENT", "51200"))
LOCAL_AGENT_URL = f"http://127.0.0.1:{PORT_AGENT}/ask"
LOCAL_AGENT_STREAM_URL = f"http://127.0.0.1:{PORT_AGENT}/ask_stream"
LOCAL_AGENT_CANCEL_URL = f"http://127.0.0.1:{PORT_AGENT}/cancel"
LOCAL_LOGIN_URL = f"http://127.0.0.1:{PORT_AGENT}/login"
LOCAL_TOOLS_URL = f"http://127.0.0.1:{PORT_AGENT}/tools"
LOCAL_SESSIONS_URL = f"http://127.0.0.1:{PORT_AGENT}/sessions"
LOCAL_SESSION_HISTORY_URL = f"http://127.0.0.1:{PORT_AGENT}/session_history"
LOCAL_DELETE_SESSION_URL = f"http://127.0.0.1:{PORT_AGENT}/delete_session"
LOCAL_TTS_URL = f"http://127.0.0.1:{PORT_AGENT}/tts"
LOCAL_SESSION_STATUS_URL = f"http://127.0.0.1:{PORT_AGENT}/session_status"
# OpenAI 兼容端点
LOCAL_OPENAI_COMPLETIONS_URL = f"http://127.0.0.1:{PORT_AGENT}/v1/chat/completions"
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "")

# OASIS Forum proxy
PORT_OASIS = int(os.getenv("PORT_OASIS", "51202"))
OASIS_BASE_URL = f"http://127.0.0.1:{PORT_OASIS}"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>Xavier AnyControl | AI Agent</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">

    <!-- PWA / iOS Full-screen support -->
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="AnyControl">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="theme-color" content="#111827">
    <meta name="format-detection" content="telephone=no">
    <meta name="msapplication-tap-highlight" content="no">
    <meta name="msapplication-TileColor" content="#111827">
    <link rel="apple-touch-icon" href="https://img.icons8.com/fluency/180/robot-2.png">
    <link rel="apple-touch-icon" sizes="152x152" href="https://img.icons8.com/fluency/152/robot-2.png">
    <link rel="apple-touch-icon" sizes="180x180" href="https://img.icons8.com/fluency/180/robot-2.png">
    <link rel="apple-touch-icon" sizes="167x167" href="https://img.icons8.com/fluency/167/robot-2.png">
    <!-- iOS splash screens -->
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <link rel="manifest" href="/manifest.json">
    
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/marked/9.1.2/marked.min.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/styles/github-dark.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/highlight.min.js"></script>

    <style>
        /* === PWA Standalone Mode Fix === */
        :root {
            --app-height: 100vh;
            --header-height: 60px;
            --input-height: 70px;
            --safe-top: env(safe-area-inset-top, 0px);
            --safe-bottom: env(safe-area-inset-bottom, 0px);
        }
        
        /* PWA standalone mode: use dynamic viewport height */
        @supports (height: 100dvh) {
            :root { --app-height: 100dvh; }
        }
        
        /* === Native App Behavior (mobile only) === */
        html, body {
            overscroll-behavior: none;
        }
        @media (hover: none) and (pointer: coarse) {
            /* Mobile / touch devices only */
            html, body {
                -webkit-overflow-scrolling: touch;
                -webkit-user-select: none;
                user-select: none;
                -webkit-touch-callout: none;
                -webkit-tap-highlight-color: transparent;
                touch-action: manipulation;
                position: fixed;
                width: 100%;
                height: 100%;
                overflow: hidden;
            }
            /* Allow text selection only inside chat messages on mobile */
            .message-agent, .message-user, .markdown-body {
                -webkit-user-select: text;
                user-select: text;
            }
        }
        /* Safe area classes removed — no special notch/curved-screen handling */
        /* Splash screen */
        #app-splash {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: linear-gradient(135deg, #111827 0%, #1e3a5f 100%);
            display: flex; flex-direction: column; align-items: center; justify-content: center;
            z-index: 99999; transition: opacity 0.5s ease;
        }
        #app-splash.fade-out { opacity: 0; pointer-events: none; }
        #app-splash .splash-icon { width: 80px; height: 80px; border-radius: 20px; margin-bottom: 16px; animation: splash-bounce 1s ease infinite; }
        #app-splash .splash-title { color: white; font-size: 22px; font-weight: 700; letter-spacing: 1px; }
        #app-splash .splash-sub { color: rgba(255,255,255,0.5); font-size: 12px; margin-top: 8px; }
        @keyframes splash-bounce { 0%,100% { transform: scale(1); } 50% { transform: scale(1.08); } }
        /* Offline banner */
        #offline-banner {
            display: none; position: fixed; top: 0; left: 0; right: 0;
            background: #ef4444; color: white; text-align: center;
            padding: 6px 0; font-size: 13px; font-weight: 600; z-index: 99998;
            padding-top: 6px;
        }
        #offline-banner.show { display: block; animation: slideDown 0.3s ease; }
        @keyframes slideDown { from { transform: translateY(-100%); } to { transform: translateY(0); } }

        /* Fixed header height - input area auto-sizes */
        header { 
            flex-shrink: 0; 
            height: auto; 
            min-height: calc(var(--header-height, 60px) + var(--safe-top)); 
            padding-top: var(--safe-top);
            z-index: 50;
        }
        .p-2.sm\:p-4.border-t { 
            flex-shrink: 0; 
            min-height: calc(60px + var(--safe-bottom));
            padding-bottom: var(--safe-bottom);
        }

        .chat-container { flex: 1; min-height: 0; overflow-y: auto; }
        .markdown-body pre { background: #1e1e1e; padding: 1rem; border-radius: 0.5rem; margin: 0.5rem 0; overflow-x: auto; }
        .markdown-body code { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 0.9em; }
        .message-user { border-radius: 1.25rem 1.25rem 0.2rem 1.25rem; }
        .message-agent { border-radius: 1.25rem 1.25rem 1.25rem 0.2rem; }
        /* TTS 朗读按钮 */
        .tts-btn {
            display: inline-flex; align-items: center; gap: 4px;
            padding: 3px 10px; margin-top: 8px;
            background: #f3f4f6; border: 1px solid #e5e7eb; border-radius: 9999px;
            font-size: 12px; color: #6b7280; cursor: pointer; user-select: none;
            transition: all 0.2s ease;
        }
        .tts-btn:hover { background: #e5e7eb; color: #374151; }
        .tts-btn.playing { background: #dbeafe; color: #2563eb; border-color: #93c5fd; }
        .tts-btn.loading { opacity: 0.6; pointer-events: none; }
        .tts-btn svg { width: 14px; height: 14px; }
        .tts-btn .tts-spinner {
            width: 14px; height: 14px; border: 2px solid #93c5fd;
            border-top-color: transparent; border-radius: 50%;
            animation: tts-spin 0.8s linear infinite; display: none;
        }
        .tts-btn.loading .tts-spinner { display: inline-block; }
        .tts-btn.loading .tts-icon { display: none; }
        @keyframes tts-spin { to { transform: rotate(360deg); } }
        .dot { width: 6px; height: 6px; background: #3b82f6; border-radius: 50%; animation: pulse 1.5s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 0.3; transform: scale(0.8); } 50% { opacity: 1; transform: scale(1.2); } }
        /* Tool panel styles */
        .tool-panel { transition: max-height 0.3s ease, opacity 0.3s ease; overflow: hidden; }
        .tool-panel.collapsed { max-height: 0; opacity: 0; }
        .tool-panel.expanded { max-height: 300px; opacity: 1; overflow-y: auto; }
        .tool-tag { display: inline-flex; align-items: center; padding: 4px 10px; border-radius: 9999px; font-size: 12px; cursor: pointer; user-select: none; transition: all 0.25s ease; }
        .tool-tag.enabled { background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe; }
        .tool-tag.enabled:hover { background: #dbeafe; }
        .tool-tag.disabled { background: #f3f4f6; color: #9ca3af; border: 1px solid #e5e7eb; opacity: 0.65; }
        .tool-tag.disabled:hover { background: #e5e7eb; opacity: 0.8; }
        .tool-toggle-btn { cursor: pointer; user-select: none; transition: color 0.2s; }
        .tool-toggle-btn:hover { color: #2563eb; }
        .tool-toggle-icon { display: inline-block; transition: transform 0.3s ease; }
        .tool-toggle-icon.open { transform: rotate(180deg); }

        /* OASIS Panel Styles */
        .oasis-panel { width: 380px; min-width: 320px; transition: width 0.3s ease; }
        .oasis-panel.collapsed-panel { width: 48px; min-width: 48px; }
        .oasis-panel.collapsed-panel .oasis-content { display: none; }
        .oasis-panel.collapsed-panel .oasis-expand-btn { display: flex; }
        .oasis-expand-btn { display: none; writing-mode: vertical-lr; text-orientation: mixed; }
        .oasis-topic-item { transition: all 0.2s ease; cursor: pointer; }
        .oasis-topic-item:hover { background: #eff6ff; }
        .oasis-topic-item.active { background: #dbeafe; border-left: 3px solid #2563eb; }
        .oasis-post { animation: slideIn 0.3s ease; }
        @keyframes slideIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
        .oasis-vote-bar { height: 6px; border-radius: 3px; overflow: hidden; }
        .oasis-vote-up { background: #22c55e; }
        .oasis-vote-down { background: #ef4444; }
        .oasis-status-badge { font-size: 10px; padding: 2px 8px; border-radius: 9999px; font-weight: 600; }
        .oasis-status-pending { background: #fef3c7; color: #92400e; }
        .oasis-status-discussing { background: #dbeafe; color: #1e40af; animation: pulse-bg 2s infinite; }
        .oasis-status-concluded { background: #d1fae5; color: #065f46; }
        .oasis-action-btn { font-size: 12px; padding: 2px 4px; border-radius: 4px; border: none; cursor: pointer; opacity: 0; transition: opacity 0.2s; background: transparent; line-height: 1; }
        .oasis-topic-item:hover .oasis-action-btn { opacity: 0.7; }
        .oasis-action-btn:hover { opacity: 1 !important; }
        .oasis-btn-cancel:hover { background: #fef3c7; }
        .oasis-btn-delete:hover { background: #fee2e2; }
        .oasis-detail-action-btn { font-size: 11px; padding: 3px 8px; border-radius: 6px; border: 1px solid #e5e7eb; cursor: pointer; background: white; transition: all 0.15s; }
        .oasis-detail-action-btn:hover { background: #f3f4f6; }
        .oasis-detail-action-btn.cancel { color: #d97706; border-color: #fbbf24; }
        .oasis-detail-action-btn.cancel:hover { background: #fffbeb; }
        .oasis-detail-action-btn.delete { color: #dc2626; border-color: #fca5a5; }
        .oasis-detail-action-btn.delete:hover { background: #fef2f2; }
        .oasis-status-error { background: #fee2e2; color: #991b1b; }
        @keyframes pulse-bg { 0%, 100% { opacity: 1; } 50% { opacity: 0.7; } }
        .oasis-expert-avatar { width: 28px; height: 28px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; font-weight: bold; color: white; flex-shrink: 0; }
        .expert-creative { background: linear-gradient(135deg, #f59e0b, #f97316); }
        .expert-critical { background: linear-gradient(135deg, #ef4444, #dc2626); }
        .expert-data { background: linear-gradient(135deg, #3b82f6, #2563eb); }
        .expert-synthesis { background: linear-gradient(135deg, #8b5cf6, #7c3aed); }
        .expert-default { background: linear-gradient(135deg, #6b7280, #4b5563); }
        .oasis-discussion-box { height: calc(100vh - 340px); overflow-y: auto; }
        .oasis-conclusion-box { background: linear-gradient(135deg, #f0fdf4, #ecfdf5); border: 1px solid #86efac; border-radius: 12px; padding: 12px; }

        /* === Page Switch Tab === */
        .page-tab-bar {
            display: flex; background: #f9fafb; border-bottom: 1px solid #e5e7eb;
            flex-shrink: 0; z-index: 10;
        }
        .page-tab {
            flex: 1; padding: 10px 0; text-align: center; font-size: 13px; font-weight: 600;
            color: #6b7280; cursor: pointer; transition: all 0.2s; border-bottom: 2px solid transparent;
            user-select: none;
        }
        .page-tab:hover { color: #374151; background: #f3f4f6; }
        .page-tab.active { color: #2563eb; border-bottom-color: #2563eb; background: white; }

        /* === Group Chat Styles === */
        .group-page { display: none; flex-direction: column; height: 100%; overflow: hidden; }
        .group-page.active { display: flex; }
        .chat-page { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
        .chat-page.hidden-page { display: none; }

        .group-list-sidebar {
            width: 240px; flex-shrink: 0; border-right: 1px solid #e5e7eb;
            display: flex; flex-direction: column; height: 100%; background: #fafbfc;
        }
        .group-item {
            padding: 10px 12px; cursor: pointer; transition: background 0.15s;
            border-bottom: 1px solid #f3f4f6; position: relative;
        }
        .group-item:hover { background: #f3f4f6; }
        .group-item.active { background: #eff6ff; border-left: 3px solid #2563eb; }
        .group-item .group-name { font-size: 13px; font-weight: 600; color: #374151; }
        .group-item .group-meta { font-size: 11px; color: #9ca3af; margin-top: 2px; }
        .group-item .group-delete-btn {
            display: none; position: absolute; right: 6px; top: 50%; transform: translateY(-50%);
            background: #fee2e2; color: #dc2626; border: none; border-radius: 4px;
            font-size: 11px; padding: 2px 6px; cursor: pointer;
        }
        .group-item:hover .group-delete-btn { display: block; }

        .group-chat-area {
            flex: 1; display: flex; flex-direction: column; min-width: 0;
        }
        .group-chat-header {
            padding: 12px 16px; border-bottom: 1px solid #e5e7eb; background: white;
            display: flex; align-items: center; justify-content: space-between; flex-shrink: 0;
        }
        .group-messages-box {
            flex: 1; overflow-y: auto; padding: 16px; space-y: 3; background: #f9fafb;
        }
        .group-msg {
            margin-bottom: 10px; animation: slideIn 0.2s ease;
        }
        .group-msg-sender {
            font-size: 11px; font-weight: 600; color: #6b7280; margin-bottom: 2px;
        }
        .group-msg-content {
            display: inline-block; padding: 8px 12px; border-radius: 12px;
            font-size: 13px; line-height: 1.5; max-width: 85%; word-break: break-word;
        }
        .group-msg-content.markdown-body { text-align: left; }
        .group-msg-content.markdown-body p { margin: 0 0 0.4em 0; }
        .group-msg-content.markdown-body p:last-child { margin-bottom: 0; }
        .group-msg-content.markdown-body pre { background: #1e1e1e; padding: 0.6rem; border-radius: 0.4rem; margin: 0.4rem 0; overflow-x: auto; }
        .group-msg-content.markdown-body code { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 0.85em; }
        .group-msg-content.markdown-body ul, .group-msg-content.markdown-body ol { margin: 0.3em 0; padding-left: 1.5em; }
        .group-msg.self .group-msg-content.markdown-body pre { background: #1e40af; }
        .group-msg.self .group-msg-content.markdown-body code { color: #e0e7ff; }
        .group-msg.self .group-msg-content { background: #2563eb; color: white; }
        .group-msg.other .group-msg-content { background: white; border: 1px solid #e5e7eb; color: #374151; }
        .group-msg.agent .group-msg-content { border-width: 1px; border-style: solid; }
        .group-msg.self { text-align: right; }
        .group-msg.agent { text-align: left; }
        .group-msg-time { font-size: 10px; color: #9ca3af; margin-top: 2px; }

        .group-input-area {
            padding: 12px 16px; border-top: 1px solid #e5e7eb; background: white; flex-shrink: 0;
            display: flex; align-items: end; gap: 8px;
        }
        .group-input-area textarea {
            flex: 1; resize: none; border: 1px solid #d1d5db; border-radius: 10px;
            padding: 8px 12px; font-size: 14px; max-height: 100px;
            outline: none; transition: border-color 0.2s;
        }
        .group-input-area textarea:focus { border-color: #2563eb; }

        /* Group member panel (right side) */
        .group-member-panel {
            width: 220px; flex-shrink: 0; border-left: 1px solid #e5e7eb;
            display: flex; flex-direction: column; background: white; overflow: hidden;
        }
        .group-member-panel .panel-header {
            padding: 12px; border-bottom: 1px solid #e5e7eb; font-size: 13px;
            font-weight: 600; color: #374151; background: #f9fafb;
        }
        .member-list { flex: 1; overflow-y: auto; padding: 8px; }
        .member-item {
            display: flex; align-items: center; justify-content: space-between;
            padding: 6px 8px; border-radius: 8px; margin-bottom: 4px; font-size: 12px;
        }
        .member-item .member-name { color: #374151; font-weight: 500; }
        .member-item .member-badge {
            font-size: 10px; padding: 1px 6px; border-radius: 9999px;
        }
        .member-item .badge-owner { background: #fef3c7; color: #92400e; }
        .member-item .badge-agent { background: #dbeafe; color: #1e40af; }

        .session-checkbox {
            display: flex; align-items: center; padding: 6px 8px; border-radius: 8px;
            cursor: pointer; transition: background 0.15s; font-size: 12px;
        }
        .session-checkbox:hover { background: #f3f4f6; }
        .session-checkbox input { margin-right: 8px; }
        .session-checkbox .session-label { color: #374151; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

        .group-empty-state {
            flex: 1; display: flex; align-items: center; justify-content: center;
            flex-direction: column; color: #9ca3af;
        }
        .group-empty-state .empty-icon { font-size: 48px; margin-bottom: 12px; }
        .group-empty-state .empty-text { font-size: 14px; }

        @media (max-width: 768px) {
            .group-list-sidebar { display: none; }
            .group-member-panel { display: none; }
            .page-tab { font-size: 12px; padding: 8px 0; }
        }

        .main-layout { display: flex; height: var(--app-height, 100vh); max-width: 100%; overflow: hidden; }
        .chat-main { flex: 1; min-width: 0; max-width: 900px; display: flex; flex-direction: column; height: var(--app-height, 100vh); overflow: hidden; }

        /* === Session sidebar === */
        .session-sidebar {
            width: 260px; flex-shrink: 0; display: flex; flex-direction: column;
            height: var(--app-height, 100vh); background: white; border-right: 1px solid #e5e7eb;
            overflow: hidden;
        }
        .session-item {
            padding: 8px 10px; border-radius: 8px; cursor: pointer; transition: background 0.15s;
            border: 1px solid transparent;
        }
        .session-item:hover { background: #f3f4f6; }
        .session-item.active { background: #eff6ff; border-color: #bfdbfe; }
        .session-item .session-title { font-size: 13px; font-weight: 500; color: #374151; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .session-item .session-meta { font-size: 11px; color: #9ca3af; margin-top: 2px; }
        .session-item .session-delete {
            display: none; position: absolute; right: 6px; top: 50%; transform: translateY(-50%);
            background: #fee2e2; color: #dc2626; border: none; border-radius: 4px;
            font-size: 11px; padding: 2px 6px; cursor: pointer; line-height: 1.2;
        }
        .session-item { position: relative; }
        .session-item:hover .session-delete { display: block; }
        .session-item .session-delete:hover { background: #fca5a5; }

        /* === Mobile responsive === */
        @media (max-width: 768px) {
            .session-sidebar {
                position: fixed; left: 0; top: 0; z-index: 200; width: 75vw; max-width: 300px;
                box-shadow: 4px 0 20px rgba(0,0,0,0.15);
            }
            .session-overlay {
                position: fixed; inset: 0; background: rgba(0,0,0,0.3); z-index: 199;
            }
            .main-layout { flex-direction: column; height: var(--app-height, 100vh); overflow: hidden; }
            .chat-main { max-width: 100%; width: 100%; height: var(--app-height, 100vh); }
            /* Header: fixed at top - auto height for safe area */
            header { 
                flex-shrink: 0; 
                height: auto; 
                min-height: calc(var(--header-height, 60px) + var(--safe-top));
                padding-top: var(--safe-top);
                overflow: visible;
            }
            /* Chat container: scrollable middle area */
            .chat-container { flex: 1; min-height: 0; overflow-y: auto; -webkit-overflow-scrolling: touch; }
            /* Input area: fixed at bottom - auto height */
            .p-2.sm\:p-4.border-t { 
                flex-shrink: 0; 
                min-height: calc(60px + var(--safe-bottom));
                padding-bottom: var(--safe-bottom);
            }
            /* OASIS: overlay mode on mobile */
            .oasis-divider { display: none !important; }
            .oasis-panel {
                position: fixed !important; top: 0; left: 0; right: 0; bottom: 0;
                width: 100% !important; min-width: 100% !important;
                z-index: 50; display: none;
            }
            .oasis-panel.mobile-open { display: flex !important; }
            .oasis-panel.collapsed-panel { display: none !important; }
            .oasis-panel .oasis-expand-btn { display: none !important; }
            /* Mobile: hide UID & session, hide desktop buttons, show hamburger */
            #uid-display, #session-display { display: none !important; }
            .desktop-only-btn { display: none !important; }
            .mobile-menu-btn { display: inline-flex !important; }
            /* Header: stack items on narrow screens */
            .mobile-header-top { flex-wrap: wrap; gap: 6px; }
            .mobile-header-actions { flex-wrap: wrap; gap: 4px; justify-content: flex-end; }
            /* Reduce padding on mobile */
            #chat-box { padding: 12px !important; }
            .message-agent, .message-user { max-width: 92% !important; }
            /* Increase font size on mobile */
            .message-content, .message-agent, .message-user { font-size: 16px !important; }
            .message-content p, .message-content li { font-size: 16px !important; }
            #message-input, #message-input::placeholder { font-size: 16px !important; }
            .tool-tag { font-size: 14px !important; padding: 6px 12px !important; }
        }
        /* Hide mobile-only elements on desktop */
        @media (min-width: 769px) {
            .mobile-menu-wrapper { display: none !important; }
        }
        /* Mobile menu dropdown styles */
        .mobile-menu-btn { display: none; }
        .mobile-menu-dropdown {
            position: absolute; right: 0; top: 100%; margin-top: 6px;
            background: white; border: 1px solid #e5e7eb; border-radius: 10px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.12); z-index: 100;
            min-width: 140px; overflow: hidden;
        }
        .mobile-menu-item {
            display: block; width: 100%; text-align: left;
            padding: 10px 14px; font-size: 13px; color: #374151;
            border: none; background: none; cursor: pointer;
            transition: background 0.15s;
        }
        .mobile-menu-item:hover, .mobile-menu-item:active { background: #f3f4f6; }
        .mobile-menu-item + .mobile-menu-item { border-top: 1px solid #f3f4f6; }
        .oasis-divider { width: 1px; background: #e5e7eb; cursor: col-resize; flex-shrink: 0; }
        .oasis-divider:hover { background: #3b82f6; width: 3px; }

        /* Image upload styles */
        .image-preview-area { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 6px; }
        .image-preview-item { position: relative; width: 60px; height: 60px; border-radius: 8px; overflow: hidden; border: 1px solid #e5e7eb; }
        .image-preview-item img { width: 100%; height: 100%; object-fit: cover; }
        .image-preview-item .remove-btn { position: absolute; top: -2px; right: -2px; width: 18px; height: 18px; background: #ef4444; color: white; border: none; border-radius: 50%; font-size: 10px; cursor: pointer; display: flex; align-items: center; justify-content: center; line-height: 1; }
        .image-upload-btn { cursor: pointer; color: #6b7280; transition: color 0.2s; flex-shrink: 0; display: flex; align-items: center; justify-content: center; width: 42px; height: 42px; border-radius: 10px; border: 1px solid #e5e7eb; background: #f9fafb; }
        .image-upload-btn:hover { color: #2563eb; border-color: #bfdbfe; background: #eff6ff; }
        @media (max-width: 768px) { .image-upload-btn { width: 36px; height: 36px; } }
        /* File preview (text files) */
        .file-preview-item { position: relative; display: flex; align-items: center; gap: 4px; padding: 4px 8px; border-radius: 8px; border: 1px solid #e5e7eb; background: #f9fafb; font-size: 12px; color: #374151; max-width: 180px; }
        .file-preview-item .file-icon { font-size: 16px; flex-shrink: 0; }
        .file-preview-item .file-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .file-preview-item .remove-btn { width: 16px; height: 16px; background: #ef4444; color: white; border: none; border-radius: 50%; font-size: 9px; cursor: pointer; display: flex; align-items: center; justify-content: center; line-height: 1; flex-shrink: 0; }
        .chat-file-tag { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border-radius: 6px; background: rgba(255,255,255,0.15); font-size: 12px; margin-bottom: 4px; }
        /* Audio recording button */
        .audio-record-btn { cursor: pointer; color: #6b7280; transition: all 0.2s; flex-shrink: 0; display: flex; align-items: center; justify-content: center; width: 42px; height: 42px; border-radius: 10px; border: 1px solid #e5e7eb; background: #f9fafb; font-size: 18px; }
        .audio-record-btn:hover { color: #dc2626; border-color: #fecaca; background: #fef2f2; }
        .audio-record-btn.recording { color: #fff; background: #dc2626; border-color: #dc2626; animation: pulse-red 1.2s infinite; }
        @keyframes pulse-red { 0%,100% { box-shadow: 0 0 0 0 rgba(220,38,38,0.4); } 50% { box-shadow: 0 0 0 8px rgba(220,38,38,0); } }
        @media (max-width: 768px) { .audio-record-btn { width: 36px; height: 36px; font-size: 16px; } }
        /* Audio preview */
        .audio-preview-item { position: relative; display: flex; align-items: center; gap: 4px; padding: 4px 8px; border-radius: 8px; border: 1px solid #e5e7eb; background: #fef2f2; font-size: 12px; color: #374151; max-width: 200px; }
        .audio-preview-item .file-icon { font-size: 16px; flex-shrink: 0; }
        .audio-preview-item .file-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .audio-preview-item .remove-btn { width: 16px; height: 16px; background: #ef4444; color: white; border: none; border-radius: 50%; font-size: 9px; cursor: pointer; display: flex; align-items: center; justify-content: center; line-height: 1; flex-shrink: 0; }
        .chat-audio-tag { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border-radius: 6px; background: rgba(255,255,255,0.15); font-size: 12px; margin-bottom: 4px; }
        /* Inline image in chat messages */
        .chat-inline-image { max-width: 240px; max-height: 180px; border-radius: 8px; margin: 4px 0; cursor: pointer; }
        .chat-inline-image:hover { opacity: 0.9; }
    </style>
</head>
<body class="bg-gray-100 font-sans leading-normal tracking-normal">

    <!-- Splash Screen -->
    <div id="app-splash">
        <img class="splash-icon" src="https://img.icons8.com/fluency/180/robot-2.png" alt="">
        <div class="splash-title">AnyControl</div>
        <div class="splash-sub">Xavier AI Agent</div>
    </div>

    <!-- Offline Banner -->
    <div id="offline-banner" data-i18n="offline_banner">⚠️ 网络已断开，请检查连接</div>

    <!-- ========== 登录页 ========== -->
    <div id="login-screen" class="min-h-screen flex items-center justify-center safe-top safe-bottom px-4" style="width:100%;height:100%;overflow:auto;">
        <div class="bg-white rounded-2xl shadow-2xl p-6 sm:p-8 w-full max-w-md border">
            <div class="flex items-center justify-center space-x-3 mb-6">
                <div class="bg-blue-600 p-3 rounded-xl text-white font-bold text-2xl">X</div>
                <h1 class="text-2xl font-bold text-gray-800" data-i18n="login_title">Xavier AnyControl</h1>
            </div>
            <p class="text-center text-gray-500 text-sm mb-8" data-i18n="login_subtitle">请登录以开始对话</p>
            <div class="space-y-4">
                <input id="username-input" type="text" maxlength="32"
                    class="w-full p-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 text-center text-lg"
                    data-i18n-placeholder="username" placeholder="用户名" autofocus>
                <input id="password-input" type="password" maxlength="64"
                    class="w-full p-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 text-center text-lg"
                    data-i18n-placeholder="password" placeholder="密码">
                <div id="login-error" class="text-red-500 text-sm text-center hidden"></div>
                <button onclick="handleLogin()" id="login-btn"
                    class="w-full bg-blue-600 hover:bg-blue-700 text-white py-3 rounded-xl font-bold text-lg transition-all shadow-lg"
                    data-i18n="login_btn">登录</button>
            </div>
            <p class="text-xs text-gray-400 text-center mt-6" data-i18n="login_footer">身份验证后方可使用，对话和文件按用户隔离</p>
        </div>
    </div>

    <!-- ========== 主布局（聊天 + OASIS）（初始隐藏） ========== -->
    <div id="chat-screen" class="main-layout safe-top safe-bottom safe-left safe-right" style="display:none;">

        <!-- ===== 历史会话侧边栏 ===== -->
        <div id="session-sidebar" class="session-sidebar" style="display:none;">
            <div class="p-3 border-b bg-gray-50 flex justify-between items-center flex-shrink-0">
                <span class="text-sm font-bold text-gray-700" data-i18n="history_title">💬 历史对话</span>
                <div class="flex items-center gap-2">
                    <button onclick="deleteAllSessions()" class="text-xs text-red-400 hover:text-red-600" data-i18n="delete_all">🗑️ 清空全部</button>
                    <button onclick="closeSessionSidebar()" class="text-gray-400 hover:text-gray-600 text-lg leading-none">&times;</button>
                </div>
            </div>
            <div id="session-list" class="flex-1 overflow-y-auto p-2 space-y-1">
                <div class="text-xs text-gray-400 text-center py-4" data-i18n="loading">加载中...</div>
            </div>
        </div>

        <!-- ===== 左侧：聊天区 ===== -->
        <div class="chat-main h-screen flex flex-col bg-white border-x border-gray-200 shadow-2xl">
            <!-- Page Switch Tab Bar -->
            <div class="page-tab-bar">
                <div class="page-tab active" id="tab-chat" onclick="switchPage('chat')" data-i18n="tab_chat">💬 对话</div>
                <div class="page-tab" id="tab-group" onclick="switchPage('group')" data-i18n="tab_group">👥 群聊</div>
            </div>

            <!-- === Chat Page === -->
            <div id="page-chat" class="chat-page">
            <header class="p-3 sm:p-4 border-b bg-white flex justify-between items-start sm:items-center gap-2 flex-shrink-0">
                <div class="flex items-center space-x-2 sm:space-x-3 mobile-header-top flex-shrink-0">
                    <div class="bg-blue-600 p-1.5 sm:p-2 rounded-lg text-white font-bold text-lg sm:text-xl">X</div>
                    <div>
                        <h1 class="text-sm sm:text-lg font-bold text-gray-800 leading-tight">AnyControl</h1>
                        <p class="text-[10px] sm:text-xs text-green-500 flex items-center" data-i18n="encrypted">● 已加密</p>
                    </div>
                </div>
                <div class="flex items-center space-x-1 sm:space-x-2 mobile-header-actions flex-shrink-0">
                    <div id="uid-display" class="text-xs sm:text-sm font-mono bg-gray-100 px-2 sm:px-3 py-1 rounded border truncate max-w-[80px] sm:max-w-none"></div>
                    <div id="session-display" class="text-[10px] sm:text-xs font-mono bg-blue-50 text-blue-600 px-1.5 sm:px-2 py-1 rounded border border-blue-200 cursor-default" data-i18n-title="current_session" title="当前对话号"></div>
                    <!-- History Button -->
                    <button onclick="toggleSessionSidebar()" class="desktop-only-btn text-[10px] sm:text-xs bg-gray-50 text-gray-600 hover:bg-gray-100 px-2 py-1 rounded border border-gray-200 transition-colors flex items-center justify-center" data-i18n-title="history_title" title="历史对话">
                        <span class="hidden sm:inline" data-i18n="history">📋历史</span>
                        <span class="sm:hidden text-base leading-none">📋</span>
                    </button>
                    <!-- New Session Button: Visible on all devices -->
                    <button onclick="handleNewSession()" class="text-[10px] sm:text-xs bg-green-50 text-green-600 hover:bg-green-100 px-2 py-1 rounded border border-green-200 transition-colors mr-1 flex items-center justify-center" data-i18n-title="new_session_confirm" title="开启新对话">
                        <span class="sm:hidden text-base font-bold leading-none">+</span>
                        <span class="hidden sm:inline" data-i18n="new_chat">+新</span>
                    </button>
                    <button onclick="toggleLanguage()" id="lang-toggle-btn" class="text-[10px] sm:text-xs bg-purple-50 text-purple-600 hover:bg-purple-100 px-2 py-1 rounded border border-purple-200 transition-colors" title="Switch Language">EN</button>
                    <button onclick="handleLogout()" class="desktop-only-btn text-[10px] sm:text-xs text-gray-400 hover:text-red-500 px-1.5 sm:px-2 py-1 rounded transition-colors" data-i18n="logout" data-i18n-title="logout" title="切换用户">退出</button>
                    <!-- Mobile: hamburger menu -->
                    <div class="mobile-menu-wrapper" style="position:relative;">
                        <button onclick="toggleMobileMenu()" class="mobile-menu-btn text-[10px] bg-gray-100 hover:bg-gray-200 px-2 py-1 rounded border border-gray-300 transition-colors" data-i18n-title="more_actions" title="更多操作">⋮</button>
                        <div id="mobile-menu-dropdown" class="mobile-menu-dropdown" style="display:none;">
                            <button onclick="toggleSessionSidebar(); closeMobileMenu();" class="mobile-menu-item" data-i18n="menu_history">📋 历史对话</button>
                            <button onclick="handleNewSession(); closeMobileMenu();" class="mobile-menu-item" data-i18n="menu_new">➕ 新对话</button>
                            <button onclick="toggleOasisMobile(); closeMobileMenu();" class="mobile-menu-item" data-i18n="menu_oasis">🏛️ OASIS</button>
                            <button onclick="handleLogout(); closeMobileMenu();" class="mobile-menu-item text-red-500" data-i18n="menu_logout">🚪 退出</button>
                        </div>
                    </div>
                </div>
            </header>

            <div id="chat-box" class="chat-container overflow-y-auto p-4 sm:p-6 space-y-4 sm:space-y-6 flex-grow bg-gray-50">
                <div class="flex justify-start">
                    <div class="message-agent bg-white border p-4 max-w-[85%] shadow-sm text-gray-700" data-i18n="welcome_message">
                        你好！我是 Xavier 智能助手。我已经准备好为你服务，请输入你的指令。
                    </div>
                </div>
            </div>

            <div class="p-2 sm:p-4 border-t bg-white flex-shrink-0">
                <!-- Tool List Panel -->
                <div id="tool-panel-wrapper" class="mb-2" style="display:none;">
                    <div class="flex items-center justify-between mb-1">
                        <div class="tool-toggle-btn flex items-center space-x-1 text-sm text-gray-500 font-medium" onclick="toggleToolPanel()">
                            <span data-i18n="available_tools">🧰 可用工具</span>
                            <span id="tool-count" class="text-xs text-gray-400"></span>
                            <span id="tool-toggle-icon" class="tool-toggle-icon text-xs">▼</span>
                        </div>
                    </div>
                    <div id="tool-panel" class="tool-panel collapsed">
                        <div id="tool-list" class="flex flex-wrap gap-2 p-2 bg-gray-50 rounded-xl border border-gray-200">
                            <!-- tools will be injected here -->
                        </div>
                    </div>
                </div>
                <div id="image-preview-area" class="image-preview-area" style="display:none;"></div>
                <div id="file-preview-area" class="image-preview-area" style="display:none;"></div>
                <div id="audio-preview-area" class="image-preview-area" style="display:none;"></div>
                <div class="flex items-end space-x-2 sm:space-x-3">
                    <label class="image-upload-btn" title="上传图片/文件/音频">
                        📎
                        <input type="file" id="image-input" accept="image/*,.pdf,.txt,.md,.csv,.json,.xml,.yaml,.yml,.log,.py,.js,.ts,.html,.css,.java,.c,.cpp,.h,.go,.rs,.sh,.bat,.ini,.toml,.cfg,.conf,.sql,.r,.rb,.mp3,.wav,.ogg,.m4a,.webm,.flac,.aac" multiple style="display:none;" onchange="handleFileSelect(event)">
                    </label>
                    <button id="record-btn" class="audio-record-btn" data-i18n-title="recording_title" title="录音" onclick="toggleRecording()">🎤</button>
                    <div class="flex-grow">
                        <textarea id="user-input" rows="1" 
                            class="w-full p-2 sm:p-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none transition-all text-sm sm:text-base"
                            data-i18n-placeholder="input_placeholder" placeholder="输入指令...（可粘贴图片/上传文件/录音）"></textarea>
                    </div>
                    <button onclick="handleSend()" id="send-btn"
                        class="bg-blue-600 hover:bg-blue-700 text-white px-4 sm:px-6 py-2 sm:py-3 rounded-xl transition-all font-bold shadow-lg h-[42px] sm:h-[50px] text-sm sm:text-base flex-shrink-0"
                        data-i18n="send_btn">发送
                    </button>
                    <button onclick="handleCancel()" id="cancel-btn"
                        class="bg-red-500 hover:bg-red-600 text-white px-4 sm:px-6 py-2 sm:py-3 rounded-xl transition-all font-bold shadow-lg h-[42px] sm:h-[50px] text-sm sm:text-base flex-shrink-0"
                        style="display:none;" data-i18n="cancel_btn">终止
                    </button>
                </div>
                <p class="text-[10px] text-center text-gray-400 mt-2 sm:mt-3 font-mono hidden sm:block" data-i18n="secure_footer">Secured by Nginx Reverse Proxy & SSH Tunnel</p>
            </div>
        </div>
        <!-- end of chat-page -->

        <!-- === Group Chat Page === -->
        <div id="page-group" class="group-page">
            <div style="display:flex; flex:1; overflow:hidden;">
                <!-- Group list sidebar -->
                <div class="group-list-sidebar">
                    <div class="p-3 border-b bg-gray-50 flex justify-between items-center flex-shrink-0">
                        <span class="text-sm font-bold text-gray-700" data-i18n="group_title">👥 群聊列表</span>
                        <button onclick="showCreateGroupModal()" class="text-xs bg-blue-50 text-blue-600 hover:bg-blue-100 px-2 py-1 rounded border border-blue-200" data-i18n="group_new">+ 新建</button>
                    </div>
                    <div id="group-list" class="flex-1 overflow-y-auto">
                        <div class="group-empty-state" style="padding:40px 0;">
                            <div class="empty-icon">👥</div>
                            <div class="empty-text" data-i18n="group_no_groups">暂无群聊</div>
                        </div>
                    </div>
                </div>

                <!-- Group chat main area -->
                <div class="group-chat-area" id="group-chat-area">
                    <div class="group-empty-state" id="group-empty-placeholder">
                        <div class="empty-icon">💬</div>
                        <div class="empty-text" data-i18n="group_select_hint">选择或创建一个群聊</div>
                    </div>
                    <!-- Active group chat (hidden initially) -->
                    <div id="group-active-chat" style="display:none; flex-direction:column; height:100%;">
                        <div class="group-chat-header">
                            <div>
                                <span id="group-active-name" class="font-bold text-gray-800 text-sm"></span>
                                <span id="group-active-id" class="text-[10px] text-gray-400 ml-2"></span>
                            </div>
                            <div class="flex items-center gap-2">
                                <button onclick="toggleGroupMemberPanel()" class="text-xs bg-gray-50 hover:bg-gray-100 px-2 py-1 rounded border border-gray-200" data-i18n="group_members_btn">👤 成员</button>
                            </div>
                        </div>
                        <div id="group-messages-box" class="group-messages-box"></div>
                        <div class="group-input-area">
                            <textarea id="group-input" rows="1" placeholder="发送消息..." data-i18n-placeholder="group_input_placeholder" onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendGroupMessage();}"></textarea>
                            <button onclick="sendGroupMessage()" class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-xl font-bold text-sm flex-shrink-0" data-i18n="send_btn">发送</button>
                        </div>
                    </div>
                </div>

                <!-- Member panel (right side) -->
                <div class="group-member-panel" id="group-member-panel" style="display:none;">
                    <div class="panel-header flex justify-between items-center">
                        <span data-i18n="group_members">成员管理</span>
                        <button onclick="toggleGroupMemberPanel()" class="text-gray-400 hover:text-gray-600 text-sm">&times;</button>
                    </div>
                    <div class="p-2 border-b">
                        <div class="text-xs font-semibold text-gray-500 mb-2" data-i18n="group_current_members">当前成员</div>
                        <div id="group-current-members" class="member-list" style="max-height:200px;"></div>
                    </div>
                    <div class="p-2 flex-1 overflow-hidden flex flex-col">
                        <div class="text-xs font-semibold text-gray-500 mb-2" data-i18n="group_add_agents">添加 Agent Session</div>
                        <div id="group-available-sessions" class="flex-1 overflow-y-auto"></div>
                    </div>
                </div>
            </div>
        </div>
        <!-- end of group-page -->
        </div>
        <!-- end of chat-main -->

        <!-- ===== 分割线 ===== -->
        <div class="oasis-divider" id="oasis-divider"></div>

        <!-- ===== 右侧：OASIS 讨论面板 ===== -->
        <div class="oasis-panel collapsed-panel bg-white border-l border-gray-200 flex flex-col h-screen" id="oasis-panel">
            <!-- Collapsed state expand button -->
            <div class="oasis-expand-btn items-center justify-center h-full text-gray-400 hover:text-blue-600 cursor-pointer text-sm font-bold" onclick="toggleOasisPanel()">
                🏛️ O A S I S
            </div>

            <!-- Panel content -->
            <div class="oasis-content flex flex-col h-full">
                <!-- Header -->
                <div class="p-3 border-b bg-gradient-to-r from-purple-50 to-blue-50 flex items-center justify-between flex-shrink-0">
                    <div class="flex items-center space-x-2">
                        <span class="text-lg">🏛️</span>
                        <div>
                            <h2 class="text-sm font-bold text-gray-800" data-i18n="oasis_title">OASIS 讨论论坛</h2>
                            <p class="text-[10px] text-gray-500" data-i18n="oasis_subtitle">多专家并行讨论系统</p>
                        </div>
                    </div>
                    <div class="flex items-center space-x-1">
                        <button onclick="refreshOasisTopics()" class="text-gray-400 hover:text-blue-600 p-1 rounded transition-colors" data-i18n-title="refresh" title="刷新">🔄</button>
                        <button onclick="toggleOasisPanel()" class="text-gray-400 hover:text-red-500 p-1 rounded transition-colors" data-i18n-title="collapse" title="收起">✕</button>
                    </div>
                </div>

                <!-- Topic list view -->
                <div id="oasis-topic-list-view" class="flex flex-col flex-1 overflow-hidden">
                    <div class="p-3 border-b flex-shrink-0">
                        <div class="flex items-center justify-between">
                            <span class="text-xs font-semibold text-gray-600" data-i18n="oasis_topics">📋 讨论话题</span>
                            <div class="flex items-center space-x-2">
                                <button onclick="deleteAllOasisTopics()" class="text-xs text-red-400 hover:text-red-600" data-i18n="delete_all">🗑️ 清空全部</button>
                                <span id="oasis-topic-count" class="text-[10px] text-gray-400"></span>
                            </div>
                        </div>
                    </div>
                    <div id="oasis-topic-list" class="flex-1 overflow-y-auto">
                        <div class="p-6 text-center text-gray-400 text-sm">
                            <div class="text-3xl mb-2">🏛️</div>
                            <p data-i18n="oasis_no_topics">暂无讨论话题</p>
                            <p class="text-xs mt-1" data-i18n="oasis_start_hint">在聊天中让 Agent 发起 OASIS 讨论</p>
                        </div>
                    </div>
                </div>

                <!-- Topic detail view (hidden by default) -->
                <div id="oasis-detail-view" class="flex flex-col flex-1 overflow-hidden" style="display:none;">
                    <!-- Detail header -->
                    <div class="p-3 border-b flex-shrink-0">
                        <div class="flex items-center justify-between">
                            <div class="flex items-center space-x-2">
                                <button onclick="showOasisTopicList()" class="text-gray-400 hover:text-blue-600 text-sm" data-i18n="oasis_back">← 返回</button>
                                <span id="oasis-detail-status" class="oasis-status-badge"></span>
                                <span id="oasis-detail-round" class="text-[10px] text-gray-400"></span>
                            </div>
                            <div id="oasis-detail-actions" class="flex items-center space-x-1">
                            </div>
                        </div>
                        <p id="oasis-detail-question" class="text-sm font-semibold text-gray-800 mt-1 line-clamp-2"></p>
                    </div>

                    <!-- Posts stream -->
                    <div id="oasis-posts-box" class="oasis-discussion-box flex-1 p-3 space-y-3 bg-gray-50">
                        <!-- Posts will be injected here -->
                    </div>

                    <!-- Conclusion area -->
                    <div id="oasis-conclusion-area" class="p-3 border-t flex-shrink-0" style="display:none;">
                        <div class="oasis-conclusion-box">
                            <div class="flex items-center space-x-1 mb-2">
                                <span class="text-sm">🏆</span>
                                <span class="text-xs font-bold text-green-800" data-i18n="oasis_conclusion">讨论结论</span>
                            </div>
                            <p id="oasis-conclusion-text" class="text-xs text-gray-700 leading-relaxed"></p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // ===== i18n 国际化配置 =====
        const i18n = {
            'zh-CN': {
                // 通用
                loading: '加载中...',
                error: '错误',
                success: '成功',
                cancel: '取消',
                confirm: '确认',
                close: '关闭',
                
                // 登录页
                login_title: 'Xavier AnyControl',
                login_subtitle: '请登录以开始对话',
                username: '用户名',
                password: '密码',
                login_btn: '登录',
                login_verifying: '验证中...',
                login_error_invalid: '用户名只能包含字母、数字、下划线、短横线或中文',
                login_error_failed: '登录失败',
                login_error_network: '网络错误',
                login_footer: '身份验证后方可使用，对话和文件按用户隔离',
                
                // 头部
                encrypted: '● 已加密',
                history: '📋历史',
                new_chat: '+新',
                new_chat_mobile: '+',
                logout: '退出',
                current_session: '当前对话号',
                more_actions: '更多操作',
                
                // 移动端菜单
                menu_history: '📋 历史对话',
                menu_new: '➕ 新对话',
                menu_oasis: '🏛️ OASIS',
                menu_logout: '🚪 退出',
                
                // 聊天区域
                welcome_message: '你好！我是 Xavier 智能助手。我已经准备好为你服务，请输入你的指令。',
                new_session_message: '🆕 已开启新对话。我是 Xavier 智能助手，请输入你的指令。',
                input_placeholder: '输入指令...（可粘贴图片/上传文件/录音）',
                send_btn: '发送',
                cancel_btn: '终止',
                no_response: '（无响应）',
                thinking_stopped: '⚠️ 已终止思考',
                login_expired: '⚠️ 登录已过期，请重新登录',
                agent_error: '❌ 错误',
                
                // 工具面板
                available_tools: '🧰 可用工具',
                tool_calling: '（调用工具中...）',
                tool_return: '🔧 工具返回',
                
                // 文件上传
                max_images: '最多上传5张图片',
                max_files: '最多上传3个文件',
                max_audios: '最多上传2个音频',
                audio_too_large: '音频过大，上限 25MB',
                pdf_too_large: 'PDF过大，上限 10MB',
                file_too_large: '文件过大，上限 512KB',
                unsupported_type: '不支持的文件类型',
                supported_types: '支持: txt, md, csv, json, py, js, pdf, mp3, wav 等',
                
                // 录音
                recording_title: '录音',
                recording_stop: '点击停止录音',
                mic_permission_denied: '无法访问麦克风，请检查浏览器权限设置。',
                recording_too_long: '录音过长，上限 25MB',
                
                // 历史会话
                history_title: '💬 历史对话',
                history_loading: '加载中...',
                history_empty: '暂无历史对话',
                history_error: '加载失败',
                history_loading_msg: '加载历史消息...',
                history_no_msg: '（此对话暂无消息记录）',
                new_session_confirm: '开启新对话？当前对话的历史记录将保留，可通过切回对话号恢复。',
                messages_count: '条消息',
                session_id: '对话号',
                delete_session: '删除',
                delete_session_confirm: '确定删除此对话？删除后不可恢复。',
                delete_all_confirm: '确定删除所有对话记录？此操作不可恢复！',
                delete_success: '删除成功',
                delete_fail: '删除失败',
                delete_all: '🗑️ 清空全部',
                
                // TTS
                tts_read: '朗读',
                tts_stop: '停止',
                tts_loading: '加载中...',
                tts_request_failed: 'TTS 请求失败',
                code_omitted: '（代码省略）',
                image_placeholder: '(图片)',
                audio_placeholder: '(语音)',
                file_placeholder: '(文件)',
                
                // OASIS
                oasis_title: 'OASIS 讨论论坛',
                oasis_subtitle: '多专家并行讨论系统',
                oasis_topics: '📋 讨论话题',
                oasis_topics_count: '个话题',
                oasis_no_topics: '暂无讨论话题',
                oasis_start_hint: '在聊天中让 Agent 发起 OASIS 讨论',
                oasis_back: '← 返回',
                oasis_conclusion: '讨论结论',
                oasis_waiting: '等待专家发言...',
                oasis_status_pending: '等待中',
                oasis_status_discussing: '讨论中',
                oasis_status_concluded: '已完成',
                oasis_status_error: '出错',
                oasis_status_cancelled: '已终止',
                oasis_round: '轮',
                oasis_posts: '帖',
                oasis_expert_creative: '创意专家',
                oasis_expert_critical: '批判专家',
                oasis_expert_data: '数据分析师',
                oasis_expert_synthesis: '综合顾问',
                oasis_cancel: '终止讨论',
                oasis_cancel_confirm: '确定要强制终止此讨论？',
                oasis_cancel_success: '讨论已终止',
                oasis_delete: '删除记录',
                oasis_delete_confirm: '确定要永久删除此讨论记录？删除后不可恢复。',
                oasis_delete_success: '记录已删除',
                oasis_action_fail: '操作失败',
                
                // 页面切换
                tab_chat: '💬 对话',
                tab_group: '👥 群聊',
                
                // 群聊
                group_title: '👥 群聊列表',
                group_new: '+ 新建',
                group_no_groups: '暂无群聊',
                group_select_hint: '选择或创建一个群聊',
                group_members_btn: '👤 成员',
                group_members: '成员管理',
                group_current_members: '当前成员',
                group_add_agents: '添加 Agent Session',
                group_input_placeholder: '发送消息...',
                group_create_title: '创建群聊',
                group_name_placeholder: '群聊名称',
                group_no_sessions: '没有可用的 Agent Session',
                group_create_btn: '创建',
                group_delete_confirm: '确定删除此群聊？',
                group_owner: '群主',
                group_agent: 'Agent',
                group_msg_count: '条消息',
                group_member_count: '人',
                
                // 离线提示
                offline_banner: '⚠️ 网络已断开，请检查连接',
                
                // 其他
                splash_subtitle: 'Xavier AI Agent',
                secure_footer: 'Secured by Nginx Reverse Proxy & SSH Tunnel',
                refresh: '刷新',
                collapse: '收起',
            },
            'en': {
                // General
                loading: 'Loading...',
                error: 'Error',
                success: 'Success',
                cancel: 'Cancel',
                confirm: 'Confirm',
                close: 'Close',
                
                // Login
                login_title: 'Xavier AnyControl',
                login_subtitle: 'Please login to start',
                username: 'Username',
                password: 'Password',
                login_btn: 'Login',
                login_verifying: 'Verifying...',
                login_error_invalid: 'Username can only contain letters, numbers, underscore, hyphen or Chinese',
                login_error_failed: 'Login failed',
                login_error_network: 'Network error',
                login_footer: 'Authentication required. Conversations and files are isolated by user',
                
                // Header
                encrypted: '● Encrypted',
                history: '📋 History',
                new_chat: '+New',
                new_chat_mobile: '+',
                logout: 'Logout',
                current_session: 'Current session',
                more_actions: 'More actions',
                
                // Mobile menu
                menu_history: '📋 History',
                menu_new: '➕ New Chat',
                menu_oasis: '🏛️ OASIS',
                menu_logout: '🚪 Logout',
                
                // Chat area
                welcome_message: 'Hello! I am Xavier AI Assistant. Ready to serve you. Please enter your instructions.',
                new_session_message: '🆕 New conversation started. I am Xavier AI Assistant. Please enter your instructions.',
                input_placeholder: 'Enter command... (paste images/upload files/record audio)',
                send_btn: 'Send',
                cancel_btn: 'Stop',
                no_response: '(No response)',
                thinking_stopped: '⚠️ Thinking stopped',
                login_expired: '⚠️ Session expired, please login again',
                agent_error: '❌ Error',
                
                // Tool panel
                available_tools: '🧰 Available Tools',
                tool_calling: '(Calling tool...)',
                tool_return: '🔧 Tool Return',
                
                // File upload
                max_images: 'Maximum 5 images',
                max_files: 'Maximum 3 files',
                max_audios: 'Maximum 2 audio files',
                audio_too_large: 'Audio too large, limit 25MB',
                pdf_too_large: 'PDF too large, limit 10MB',
                file_too_large: 'File too large, limit 512KB',
                unsupported_type: 'Unsupported file type',
                supported_types: 'Supported: txt, md, csv, json, py, js, pdf, mp3, wav, etc.',
                
                // Recording
                recording_title: 'Record',
                recording_stop: 'Click to stop recording',
                mic_permission_denied: 'Cannot access microphone. Please check browser permissions.',
                recording_too_long: 'Recording too long, limit 25MB',
                
                // History sessions
                history_title: '💬 History',
                history_loading: 'Loading...',
                history_empty: 'No history',
                history_error: 'Failed to load',
                history_loading_msg: 'Loading messages...',
                history_no_msg: '(No messages in this conversation)',
                new_session_confirm: 'Start new conversation? Current history will be preserved.',
                messages_count: 'messages',
                session_id: 'Session',
                delete_session: 'Delete',
                delete_session_confirm: 'Delete this conversation? This cannot be undone.',
                delete_all_confirm: 'Delete ALL conversations? This cannot be undone!',
                delete_success: 'Deleted',
                delete_fail: 'Delete failed',
                delete_all: '🗑️ Clear All',
                
                // TTS
                tts_read: 'Read',
                tts_stop: 'Stop',
                tts_loading: 'Loading...',
                tts_request_failed: 'TTS request failed',
                code_omitted: '(code omitted)',
                image_placeholder: '(image)',
                audio_placeholder: '(audio)',
                file_placeholder: '(file)',
                
                // OASIS
                oasis_title: 'OASIS Discussion Forum',
                oasis_subtitle: 'Multi-Expert Parallel Discussion System',
                oasis_topics: '📋 Discussion Topics',
                oasis_topics_count: 'topics',
                oasis_no_topics: 'No discussion topics',
                oasis_start_hint: 'Ask Agent to start an OASIS discussion in chat',
                oasis_back: '← Back',
                oasis_conclusion: 'Conclusion',
                oasis_waiting: 'Waiting for experts...',
                oasis_status_pending: 'Pending',
                oasis_status_discussing: 'Discussing',
                oasis_status_concluded: 'Completed',
                oasis_status_error: 'Error',
                oasis_status_cancelled: 'Cancelled',
                oasis_round: 'rounds',
                oasis_posts: 'posts',
                oasis_expert_creative: 'Creative Expert',
                oasis_expert_critical: 'Critical Expert',
                oasis_expert_data: 'Data Analyst',
                oasis_expert_synthesis: 'Synthesis Advisor',
                oasis_cancel: 'Stop Discussion',
                oasis_cancel_confirm: 'Force stop this discussion?',
                oasis_cancel_success: 'Discussion stopped',
                oasis_delete: 'Delete',
                oasis_delete_confirm: 'Permanently delete this discussion? This cannot be undone.',
                oasis_delete_success: 'Record deleted',
                oasis_action_fail: 'Action failed',
                
                // Page switch
                tab_chat: '💬 Chat',
                tab_group: '👥 Groups',
                
                // Group chat
                group_title: '👥 Group Chats',
                group_new: '+ New',
                group_no_groups: 'No group chats',
                group_select_hint: 'Select or create a group chat',
                group_members_btn: '👤 Members',
                group_members: 'Member Management',
                group_current_members: 'Current Members',
                group_add_agents: 'Add Agent Session',
                group_input_placeholder: 'Send a message...',
                group_create_title: 'Create Group Chat',
                group_name_placeholder: 'Group name',
                group_no_sessions: 'No available Agent Sessions',
                group_create_btn: 'Create',
                group_delete_confirm: 'Delete this group chat?',
                group_owner: 'Owner',
                group_agent: 'Agent',
                group_msg_count: 'messages',
                group_member_count: 'members',
                
                // Offline
                offline_banner: '⚠️ Network disconnected, please check connection',
                
                // Others
                splash_subtitle: 'Xavier AI Agent',
                secure_footer: 'Secured by Nginx Reverse Proxy & SSH Tunnel',
                refresh: 'Refresh',
                collapse: 'Collapse',
            }
        };
        
        // 当前语言
        let currentLang = localStorage.getItem('lang') || 'zh-CN';
        // 确保语言值有效
        if (!i18n[currentLang]) { currentLang = 'zh-CN'; localStorage.setItem('lang', 'zh-CN'); }
        
        // 获取翻译文本
        function t(key) {
            return (i18n[currentLang] && i18n[currentLang][key]) || i18n['zh-CN'][key] || key;
        }
        
        // 切换语言
        function toggleLanguage() {
            currentLang = currentLang === 'zh-CN' ? 'en' : 'zh-CN';
            localStorage.setItem('lang', currentLang);
            document.documentElement.lang = currentLang;
            applyTranslations();
        }
        
        // 应用翻译到页面
        function applyTranslations() {
            // 更新语言按钮显示
            const langBtn = document.getElementById('lang-toggle-btn');
            if (langBtn) {
                langBtn.textContent = currentLang === 'zh-CN' ? 'EN' : '中文';
            }
            
            // 更新 data-i18n 属性的元素
            document.querySelectorAll('[data-i18n]').forEach(el => {
                const key = el.getAttribute('data-i18n');
                if (el.tagName === 'INPUT' && el.hasAttribute('placeholder')) {
                    el.placeholder = t(key);
                } else if (el.tagName === 'TEXTAREA' && el.hasAttribute('placeholder')) {
                    el.placeholder = t(key);
                } else {
                    el.textContent = t(key);
                }
            });
            
            // 更新 data-i18n-placeholder 属性
            document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
                el.placeholder = t(el.getAttribute('data-i18n-placeholder'));
            });
            
            // 更新 title
            document.title = 'Xavier AnyControl | AI Agent';
        }
        
        marked.setOptions({
            highlight: function(code, lang) {
                const language = hljs.getLanguage(lang) ? lang : 'plaintext';
                return hljs.highlight(code, { language }).value;
            },
            langPrefix: 'hljs language-'
        });

        let currentUserId = null;
        let currentSessionId = null;
        let currentAbortController = null;
        let pendingImages = []; // [{base64: "data:image/...", name: "file.jpg"}, ...]
        let pendingFiles = [];  // [{name: "data.csv", content: "...(text content)"}, ...]
        let pendingAudios = []; // [{base64: "data:audio/...", name: "recording.wav", format: "wav"}, ...]
        let isRecording = false;

        // OpenAI API 配置
        function getAuthToken() { return sessionStorage.getItem('authToken') || ''; }
        const TEXT_EXTENSIONS = new Set(['.txt','.md','.csv','.json','.xml','.yaml','.yml','.log','.py','.js','.ts','.html','.css','.java','.c','.cpp','.h','.go','.rs','.sh','.bat','.ini','.toml','.cfg','.conf','.sql','.r','.rb']);
        const AUDIO_EXTENSIONS = new Set(['.mp3','.wav','.ogg','.m4a','.webm','.flac','.aac']);
        const MAX_FILE_SIZE = 512 * 1024; // 512KB per text file
        const MAX_PDF_SIZE = 10 * 1024 * 1024; // 10MB per PDF
        const MAX_AUDIO_SIZE = 25 * 1024 * 1024; // 25MB per audio
        const MAX_IMAGE_SIZE = 10 * 1024 * 1024; // 压缩目标：10MB
        const MAX_IMAGE_DIMENSION = 2048; // 最大边长

        function compressImage(file) {
            return new Promise((resolve) => {
                const img = new Image();
                img.onload = () => {
                    let { width, height } = img;
                    if (width > MAX_IMAGE_DIMENSION || height > MAX_IMAGE_DIMENSION) {
                        const scale = MAX_IMAGE_DIMENSION / Math.max(width, height);
                        width = Math.round(width * scale);
                        height = Math.round(height * scale);
                    }
                    const canvas = document.createElement('canvas');
                    canvas.width = width;
                    canvas.height = height;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0, width, height);
                    let quality = 0.85;
                    let result = canvas.toDataURL('image/jpeg', quality);
                    while (result.length > MAX_IMAGE_SIZE * 1.37 && quality > 0.3) {
                        quality -= 0.1;
                        result = canvas.toDataURL('image/jpeg', quality);
                    }
                    resolve(result);
                };
                img.src = URL.createObjectURL(file);
            });
        }

        // ===== File Upload Logic (images + text files + PDF + audio) =====
        function handleFileSelect(event) {
            const files = event.target.files;
            if (!files.length) return;
            for (const file of files) {
                if (file.type.startsWith('image/')) {
                    if (pendingImages.length >= 5) { alert(t('max_images')); break; }
                    if (file.size <= MAX_IMAGE_SIZE) {
                        const reader = new FileReader();
                        reader.onload = (e) => {
                            pendingImages.push({ base64: e.target.result, name: file.name });
                            renderImagePreviews();
                        };
                        reader.readAsDataURL(file);
                    } else {
                        compressImage(file).then((compressed) => {
                            pendingImages.push({ base64: compressed, name: file.name });
                            renderImagePreviews();
                        });
                    }
                } else if (file.type.startsWith('audio/') || AUDIO_EXTENSIONS.has('.' + file.name.split('.').pop().toLowerCase())) {
                    if (file.size > MAX_AUDIO_SIZE) { alert(`${file.name}: ${t('audio_too_large')} (${(file.size/1024/1024).toFixed(1)}MB)`); continue; }
                    if (pendingAudios.length >= 2) { alert(t('max_audios')); break; }
                    const ext = file.name.split('.').pop().toLowerCase();
                    const fmt = ({'mp3':'mp3','wav':'wav','ogg':'ogg','m4a':'m4a','webm':'webm','flac':'flac','aac':'aac'})[ext] || 'mp3';
                    const reader = new FileReader();
                    reader.onload = (e) => {
                        pendingAudios.push({ base64: e.target.result, name: file.name, format: fmt });
                        renderAudioPreviews();
                    };
                    reader.readAsDataURL(file);
                } else if (file.name.toLowerCase().endsWith('.pdf') || file.type === 'application/pdf') {
                    if (file.size > MAX_PDF_SIZE) { alert(`${file.name}: ${t('pdf_too_large')} (${(file.size/1024/1024).toFixed(1)}MB)`); continue; }
                    if (pendingFiles.length >= 3) { alert(t('max_files')); break; }
                    const reader = new FileReader();
                    reader.onload = (e) => {
                        pendingFiles.push({ name: file.name, content: e.target.result, type: 'pdf' });
                        renderFilePreviews();
                    };
                    reader.readAsDataURL(file);
                } else {
                    const ext = '.' + file.name.split('.').pop().toLowerCase();
                    if (!TEXT_EXTENSIONS.has(ext)) { alert(`${t('unsupported_type')}: ${ext}\\n${t('supported_types')}`); continue; }
                    if (file.size > MAX_FILE_SIZE) { alert(`${file.name}: ${t('file_too_large')} (${(file.size/1024).toFixed(0)}KB)`); continue; }
                    if (pendingFiles.length >= 3) { alert(t('max_files')); break; }
                    const reader = new FileReader();
                    reader.onload = (e) => {
                        pendingFiles.push({ name: file.name, content: e.target.result, type: 'text' });
                        renderFilePreviews();
                    };
                    reader.readAsText(file);
                }
            }
            event.target.value = '';
        }

        // ===== Audio Recording =====
        async function toggleRecording() {
            if (isRecording) {
                stopRecording();
            } else {
                await startRecording();
            }
        }

        // --- WAV 编码辅助函数 ---
        function encodeWAV(samples, sampleRate) {
            const buffer = new ArrayBuffer(44 + samples.length * 2);
            const view = new DataView(buffer);
            function writeString(offset, string) {
                for (let i = 0; i < string.length; i++) view.setUint8(offset + i, string.charCodeAt(i));
            }
            writeString(0, 'RIFF');
            view.setUint32(4, 36 + samples.length * 2, true);
            writeString(8, 'WAVE');
            writeString(12, 'fmt ');
            view.setUint32(16, 16, true);
            view.setUint16(20, 1, true); // PCM
            view.setUint16(22, 1, true); // mono
            view.setUint32(24, sampleRate, true);
            view.setUint32(28, sampleRate * 2, true);
            view.setUint16(32, 2, true);
            view.setUint16(34, 16, true);
            writeString(36, 'data');
            view.setUint32(40, samples.length * 2, true);
            for (let i = 0; i < samples.length; i++) {
                const s = Math.max(-1, Math.min(1, samples[i]));
                view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
            }
            return new Blob([buffer], { type: 'audio/wav' });
        }

        let audioContext = null;
        let audioSourceNode = null;
        let audioProcessorNode = null;
        let recordedSamples = [];

        async function startRecording() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
                audioSourceNode = audioContext.createMediaStreamSource(stream);
                audioProcessorNode = audioContext.createScriptProcessor(4096, 1, 1);
                recordedSamples = [];
                audioProcessorNode.onaudioprocess = (e) => {
                    const data = e.inputBuffer.getChannelData(0);
                    recordedSamples.push(new Float32Array(data));
                };
                audioSourceNode.connect(audioProcessorNode);
                audioProcessorNode.connect(audioContext.destination);
                isRecording = true;
                document.getElementById('record-btn').classList.add('recording');
                document.getElementById('record-btn').title = t('recording_stop');
            } catch (err) {
                alert(t('mic_permission_denied') + '\\n' + err.message);
            }
        }

        function stopRecording() {
            if (!audioContext) return;
            const stream = audioSourceNode.mediaStream;
            audioProcessorNode.disconnect();
            audioSourceNode.disconnect();
            stream.getTracks().forEach(t => t.stop());
            // 合并所有采样
            let totalLen = 0;
            for (const chunk of recordedSamples) totalLen += chunk.length;
            const merged = new Float32Array(totalLen);
            let offset = 0;
            for (const chunk of recordedSamples) { merged.set(chunk, offset); offset += chunk.length; }
            const sampleRate = audioContext.sampleRate;
            audioContext.close();
            audioContext = null;
            audioSourceNode = null;
            audioProcessorNode = null;
            recordedSamples = [];
            isRecording = false;
            document.getElementById('record-btn').classList.remove('recording');
            document.getElementById('record-btn').title = t('recording_title');
            const blob = encodeWAV(merged, sampleRate);
            if (blob.size > MAX_AUDIO_SIZE) { alert(t('recording_too_long')); return; }
            if (pendingAudios.length >= 2) { alert(t('max_audios')); return; }
            const reader = new FileReader();
            reader.onload = (e) => {
                const ts = new Date().toLocaleTimeString(currentLang === 'zh-CN' ? 'zh-CN' : 'en-US', {hour:'2-digit',minute:'2-digit',second:'2-digit'});
                const recName = currentLang === 'zh-CN' ? `录音_${ts}.wav` : `recording_${ts}.wav`;
                pendingAudios.push({ base64: e.target.result, name: recName, format: 'wav' });
                renderAudioPreviews();
            };
            reader.readAsDataURL(blob);
        }

        function removeAudio(index) {
            pendingAudios.splice(index, 1);
            renderAudioPreviews();
        }

        function renderAudioPreviews() {
            const area = document.getElementById('audio-preview-area');
            if (pendingAudios.length === 0) {
                area.style.display = 'none';
                area.innerHTML = '';
                return;
            }
            area.style.display = 'flex';
            area.innerHTML = pendingAudios.map((a, i) => `
                <div class="audio-preview-item">
                    <span class="file-icon">🎤</span>
                    <span class="file-name" title="${escapeHtml(a.name)}">${escapeHtml(a.name)}</span>
                    <button class="remove-btn" onclick="removeAudio(${i})">&times;</button>
                </div>
            `).join('');
        }

        function handlePasteImage(event) {
            const items = event.clipboardData?.items;
            if (!items) return;
            for (const item of items) {
                if (!item.type.startsWith('image/')) continue;
                event.preventDefault();
                if (pendingImages.length >= 5) { alert(t('max_images')); break; }
                const file = item.getAsFile();
                const reader = new FileReader();
                reader.onload = (e) => {
                    pendingImages.push({ base64: e.target.result, name: 'pasted_image.png' });
                    renderImagePreviews();
                };
                reader.readAsDataURL(file);
            }
        }

        function removeImage(index) {
            pendingImages.splice(index, 1);
            renderImagePreviews();
        }

        function removeFile(index) {
            pendingFiles.splice(index, 1);
            renderFilePreviews();
        }

        function renderImagePreviews() {
            const area = document.getElementById('image-preview-area');
            if (pendingImages.length === 0) {
                area.style.display = 'none';
                area.innerHTML = '';
                return;
            }
            area.style.display = 'flex';
            area.innerHTML = pendingImages.map((img, i) => `
                <div class="image-preview-item">
                    <img src="${img.base64}" alt="${img.name}">
                    <button class="remove-btn" onclick="removeImage(${i})">&times;</button>
                </div>
            `).join('');
        }

        function renderFilePreviews() {
            const area = document.getElementById('file-preview-area');
            if (pendingFiles.length === 0) {
                area.style.display = 'none';
                area.innerHTML = '';
                return;
            }
            area.style.display = 'flex';
            area.innerHTML = pendingFiles.map((f, i) => `
                <div class="file-preview-item">
                    <span class="file-icon">📄</span>
                    <span class="file-name" title="${escapeHtml(f.name)}">${escapeHtml(f.name)}</span>
                    <button class="remove-btn" onclick="removeFile(${i})">&times;</button>
                </div>
            `).join('');
        }

        // ===== Session (conversation) ID management =====
        function generateSessionId() {
            return Date.now().toString(36) + Math.random().toString(36).substr(2, 4);
        }

        function initSession() {
            let saved = sessionStorage.getItem('sessionId');
            if (!saved) {
                saved = generateSessionId();
                sessionStorage.setItem('sessionId', saved);
            }
            currentSessionId = saved;
            updateSessionDisplay();
        }

        function updateSessionDisplay() {
            const el = document.getElementById('session-display');
            if (el && currentSessionId) {
                el.textContent = '#' + currentSessionId.slice(-6);
                el.title = t('session_id') + ': ' + currentSessionId;
            }
        }

        function handleNewSession() {
            if (!confirm(t('new_session_confirm'))) return;
            currentSessionId = generateSessionId();
            sessionStorage.setItem('sessionId', currentSessionId);
            updateSessionDisplay();
            // Clear chat box for new conversation
            const chatBox = document.getElementById('chat-box');
            chatBox.innerHTML = `
                <div class="flex justify-start">
                    <div class="message-agent bg-white border p-4 max-w-[85%] shadow-sm text-gray-700">
                        ${t('new_session_message')}
                    </div>
                </div>`;
        }

        // ===== 历史会话侧边栏 =====
        let sessionSidebarOpen = false;

        function toggleSessionSidebar() {
            if (sessionSidebarOpen) { closeSessionSidebar(); } else { openSessionSidebar(); }
        }

        async function openSessionSidebar() {
            const sidebar = document.getElementById('session-sidebar');
            sidebar.style.display = 'flex';
            sessionSidebarOpen = true;
            // 移动端加遮罩
            if (window.innerWidth <= 768) {
                let overlay = document.getElementById('session-overlay');
                if (!overlay) {
                    overlay = document.createElement('div');
                    overlay.id = 'session-overlay';
                    overlay.className = 'session-overlay';
                    overlay.onclick = closeSessionSidebar;
                    sidebar.parentElement.appendChild(overlay);
                }
                overlay.style.display = 'block';
            }
            await loadSessionList();
        }

        function closeSessionSidebar() {
            document.getElementById('session-sidebar').style.display = 'none';
            const overlay = document.getElementById('session-overlay');
            if (overlay) overlay.style.display = 'none';
            sessionSidebarOpen = false;
        }

        async function loadSessionList() {
            const listEl = document.getElementById('session-list');
            listEl.innerHTML = `<div class="text-xs text-gray-400 text-center py-4">${t('loading')}</div>`;
            try {
                const resp = await fetch('/proxy_sessions');
                const data = await resp.json();
                if (!data.sessions || data.sessions.length === 0) {
                    listEl.innerHTML = `<div class="text-xs text-gray-400 text-center py-4">${t('history_empty')}</div>`;
                    return;
                }
                listEl.innerHTML = '';
                // 按 session_id 倒序（新的在前）
                data.sessions.sort((a, b) => b.session_id.localeCompare(a.session_id));
                for (const s of data.sessions) {
                    const isActive = s.session_id === currentSessionId;
                    const div = document.createElement('div');
                    div.className = 'session-item' + (isActive ? ' active' : '');
                    div.innerHTML = `
                        <div class="session-title">${escapeHtml(s.title)}</div>
                        <div class="session-meta">#${s.session_id.slice(-6)} · ${s.message_count}${t('messages_count')}</div>
                        <button class="session-delete" onclick="event.stopPropagation(); deleteSession('${s.session_id}')">${t('delete_session')}</button>
                    `;
                    div.onclick = () => switchToSession(s.session_id);
                    listEl.appendChild(div);
                }
            } catch (e) {
                listEl.innerHTML = `<div class="text-xs text-red-400 text-center py-4">${t('history_error')}</div>`;
            }
        }

        async function deleteSession(sessionId) {
            if (!confirm(t('delete_session_confirm'))) return;
            try {
                const resp = await fetch('/proxy_delete_session', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ session_id: sessionId })
                });
                const data = await resp.json();
                if (resp.ok && data.status === 'success') {
                    // 如果删除的是当前会话，自动开一个新的
                    if (sessionId === currentSessionId) {
                        currentSessionId = generateSessionId();
                        sessionStorage.setItem('sessionId', currentSessionId);
                        updateSessionDisplay();
                        document.getElementById('chat-box').innerHTML = `
                            <div class="flex justify-start">
                                <div class="message-agent bg-white border p-4 max-w-[85%] shadow-sm text-gray-700">
                                    ${t('new_session_message')}
                                </div>
                            </div>`;
                    }
                    await loadSessionList();
                } else {
                    alert(t('delete_fail') + ': ' + (data.detail || data.error || ''));
                }
            } catch (e) {
                alert(t('delete_fail') + ': ' + e.message);
            }
        }

        async function deleteAllSessions() {
            if (!confirm(t('delete_all_confirm'))) return;
            try {
                const resp = await fetch('/proxy_delete_session', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ session_id: '' })
                });
                const data = await resp.json();
                if (resp.ok && data.status === 'success') {
                    currentSessionId = generateSessionId();
                    sessionStorage.setItem('sessionId', currentSessionId);
                    updateSessionDisplay();
                    document.getElementById('chat-box').innerHTML = `
                        <div class="flex justify-start">
                            <div class="message-agent bg-white border p-4 max-w-[85%] shadow-sm text-gray-700">
                                ${t('new_session_message')}
                            </div>
                        </div>`;
                    await loadSessionList();
                } else {
                    alert(t('delete_fail') + ': ' + (data.detail || data.error || ''));
                }
            } catch (e) {
                alert(t('delete_fail') + ': ' + e.message);
            }
        }

        async function switchToSession(sessionId) {
            if (sessionId === currentSessionId) { closeSessionSidebar(); return; }
            currentSessionId = sessionId;
            sessionStorage.setItem('sessionId', sessionId);
            updateSessionDisplay();
            closeSessionSidebar();

            // 加载该会话的历史消息
            const chatBox = document.getElementById('chat-box');
            chatBox.innerHTML = `<div class="text-xs text-gray-400 text-center py-4">${t('history_loading_msg')}</div>`;

            try {
                const resp = await fetch('/proxy_session_history', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ session_id: sessionId })
                });
                const data = await resp.json();
                chatBox.innerHTML = '';

                if (!data.messages || data.messages.length === 0) {
                    chatBox.innerHTML = `
                        <div class="flex justify-start">
                            <div class="message-agent bg-white border p-4 max-w-[85%] shadow-sm text-gray-700">
                                ${t('history_no_msg')}
                            </div>
                        </div>`;
                    return;
                }

                for (const msg of data.messages) {
                    if (msg.role === 'user') {
                        // 支持多模态历史消息（content 可能是 string 或 array）
                        let textContent = '';
                        let imagesHtml = '';
                        if (typeof msg.content === 'string') {
                            textContent = msg.content;
                        } else if (Array.isArray(msg.content)) {
                            for (const part of msg.content) {
                                if (part.type === 'text') textContent = part.text || '';
                                else if (part.type === 'image_url') {
                                    imagesHtml += `<img src="${part.image_url.url}" class="chat-inline-image">`;
                                }
                            }
                        }
                        chatBox.innerHTML += `
                            <div class="flex justify-end">
                                <div class="message-user bg-blue-600 text-white p-4 max-w-[85%] shadow-sm">
                                    ${imagesHtml}${imagesHtml ? '<div style="margin-top:6px">' : ''}${escapeHtml(textContent || '('+t('image_placeholder')+')')}${imagesHtml ? '</div>' : ''}
                                </div>
                            </div>`;
                    } else if (msg.role === 'tool') {
                        chatBox.innerHTML += `
                            <div class="flex justify-start">
                                <div class="bg-gray-100 border border-dashed border-gray-300 p-3 max-w-[85%] shadow-sm text-xs text-gray-500 rounded-lg">
                                    <div class="font-semibold text-gray-600 mb-1">🔧 ${t('tool_return')}: ${escapeHtml(msg.tool_name || '')}</div>
                                    <pre class="whitespace-pre-wrap break-words">${escapeHtml(msg.content.length > 500 ? msg.content.slice(0, 500) + '...' : msg.content)}</pre>
                                </div>
                            </div>`;
                    } else {
                        let toolCallsHtml = '';
                        if (msg.tool_calls && msg.tool_calls.length > 0) {
                            const callsList = msg.tool_calls.map(tc =>
                                `<span class="inline-block bg-blue-100 text-blue-700 text-xs px-2 py-0.5 rounded mr-1 mb-1">🔧 ${escapeHtml(tc.name)}</span>`
                            ).join('');
                            toolCallsHtml = `<div class="mb-2">${callsList}</div>`;
                        }
                        chatBox.innerHTML += `
                            <div class="flex justify-start">
                                <div class="message-agent bg-white border p-4 max-w-[85%] shadow-sm text-gray-700 markdown-body" data-tts-ready="1">
                                    ${toolCallsHtml}${msg.content ? marked.parse(msg.content) : '<span class="text-gray-400 text-xs">('+t('tool_calling')+')</span>'}
                                </div>
                            </div>`;
                    }
                }
                // 为历史 AI 消息添加朗读按钮
                chatBox.querySelectorAll('[data-tts-ready="1"]').forEach(div => {
                    div.removeAttribute('data-tts-ready');
                    const ttsBtn = createTtsButton(() => div.innerText || div.textContent || '');
                    div.appendChild(ttsBtn);
                });
                // 高亮代码块
                chatBox.querySelectorAll('pre code').forEach((block) => hljs.highlightElement(block));
                chatBox.scrollTop = chatBox.scrollHeight;
            } catch (e) {
                chatBox.innerHTML = `
                    <div class="text-xs text-red-400 text-center py-4">${t('history_error')}: ${e.message}</div>`;
            }
        }

        // ===== 登录逻辑 =====
        async function handleLogin() {
            const nameInput = document.getElementById('username-input');
            const pwInput = document.getElementById('password-input');
            const errorDiv = document.getElementById('login-error');
            const loginBtn = document.getElementById('login-btn');
            const name = nameInput.value.trim();
            const password = pwInput.value;

            errorDiv.classList.add('hidden');

            if (!name) { nameInput.focus(); return; }
            if (!password) { pwInput.focus(); return; }

            if (!/^[a-zA-Z0-9_\\-\\u4e00-\\u9fa5]+$/.test(name)) {
                errorDiv.textContent = t('login_error_invalid');
                errorDiv.classList.remove('hidden');
                return;
            }

            loginBtn.disabled = true;
            loginBtn.textContent = t('login_verifying');

            try {
                const resp = await fetch("/proxy_login", {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id: name, password: password })
                });
                const data = await resp.json();
                if (!resp.ok) {
                    errorDiv.textContent = data.detail || data.error || t('login_error_failed');
                    errorDiv.classList.remove('hidden');
                    return;
                }

                currentUserId = name;
                sessionStorage.setItem('userId', name);
                // 存储 OpenAI 格式的 Bearer token: user_id:password
                const authToken = name + ':' + password;
                sessionStorage.setItem('authToken', authToken);
                initSession();

                document.getElementById('uid-display').textContent = 'UID: ' + name;
                document.getElementById('login-screen').style.display = 'none';
                document.getElementById('chat-screen').style.display = 'flex';
                document.getElementById('user-input').focus();
                loadTools();
                refreshOasisTopics(); // Load OASIS topics after login
            } catch (e) {
                errorDiv.textContent = t('login_error_network') + ': ' + e.message;
                errorDiv.classList.remove('hidden');
            } finally {
                loginBtn.disabled = false;
                loginBtn.textContent = t('login_btn');
            }
        }

        function handleLogout() {
            currentUserId = null;
            currentSessionId = null;
            sessionStorage.removeItem('userId');
            sessionStorage.removeItem('authToken');
            sessionStorage.removeItem('sessionId');
            fetch("/proxy_logout", { method: 'POST' });
            document.getElementById('chat-screen').style.display = 'none';
            document.getElementById('login-screen').style.display = 'flex';
            document.getElementById('username-input').value = '';
            document.getElementById('password-input').value = '';
            document.getElementById('login-error').classList.add('hidden');
            document.getElementById('username-input').focus();
            const chatBox = document.getElementById('chat-box');
            chatBox.innerHTML = `
                <div class="flex justify-start">
                    <div class="message-agent bg-white border p-4 max-w-[85%] shadow-sm text-gray-700">
                        ${t('welcome_message')}
                    </div>
                </div>`;
            // Stop OASIS polling
            stopOasisPolling();
        }

        // ===== Tool Panel 逻辑 =====
        let toolPanelOpen = false;
        let allTools = [];
        let enabledToolSet = new Set();

        function toggleToolPanel() {
            const panel = document.getElementById('tool-panel');
            const icon = document.getElementById('tool-toggle-icon');
            toolPanelOpen = !toolPanelOpen;
            if (toolPanelOpen) {
                panel.classList.remove('collapsed');
                panel.classList.add('expanded');
                icon.classList.add('open');
            } else {
                panel.classList.remove('expanded');
                panel.classList.add('collapsed');
                icon.classList.remove('open');
            }
        }

        function updateToolCount() {
            const toolCount = document.getElementById('tool-count');
            toolCount.textContent = '(' + enabledToolSet.size + '/' + allTools.length + ')';
        }

        function toggleTool(name, tagEl) {
            if (enabledToolSet.has(name)) {
                enabledToolSet.delete(name);
                tagEl.classList.remove('enabled');
                tagEl.classList.add('disabled');
            } else {
                enabledToolSet.add(name);
                tagEl.classList.remove('disabled');
                tagEl.classList.add('enabled');
            }
            updateToolCount();
        }

        function getEnabledTools() {
            if (enabledToolSet.size === allTools.length) return null;
            return Array.from(enabledToolSet);
        }

        async function loadTools() {
            try {
                const resp = await fetch('/proxy_tools');
                if (!resp.ok) return;
                const data = await resp.json();
                const tools = data.tools || [];
                const toolList = document.getElementById('tool-list');
                const wrapper = document.getElementById('tool-panel-wrapper');

                if (tools.length === 0) {
                    wrapper.style.display = 'none';
                    return;
                }

                allTools = tools;
                enabledToolSet = new Set(tools.map(t => t.name));
                toolList.innerHTML = '';
                tools.forEach(t => {
                    const tag = document.createElement('span');
                    tag.className = 'tool-tag enabled';
                    tag.title = t.description || '';
                    tag.textContent = t.name;
                    tag.onclick = () => toggleTool(t.name, tag);
                    toolList.appendChild(tag);
                });
                updateToolCount();
                wrapper.style.display = 'block';
            } catch (e) {
                console.warn('Failed to load tools:', e);
            }
        }

        // Session check
        (function checkSession() {
            // 初始化语言
            document.documentElement.lang = currentLang;
            applyTranslations();
            
            const saved = sessionStorage.getItem('userId');
            if (saved) {
                currentUserId = saved;
                initSession();
                document.getElementById('uid-display').textContent = 'UID: ' + saved;
                document.getElementById('login-screen').style.display = 'none';
                document.getElementById('chat-screen').style.display = 'flex';
                loadTools();
                refreshOasisTopics();
            }
        })();

        // Login input handlers
        document.getElementById('username-input').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') { e.preventDefault(); document.getElementById('password-input').focus(); }
        });
        document.getElementById('password-input').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') { e.preventDefault(); handleLogin(); }
        });

        // ===== 聊天逻辑 =====
        const chatBox = document.getElementById('chat-box');
        const inputField = document.getElementById('user-input');
        const sendBtn = document.getElementById('send-btn');
        const cancelBtn = document.getElementById('cancel-btn');

        function setStreamingUI(streaming) {
            if (streaming) {
                sendBtn.style.display = 'none';
                cancelBtn.style.display = 'inline-block';
                inputField.disabled = true;
            } else {
                sendBtn.style.display = 'inline-block';
                cancelBtn.style.display = 'none';
                sendBtn.disabled = false;
                inputField.disabled = false;
            }
        }

        async function handleCancel() {
            if (currentAbortController) {
                currentAbortController.abort();
                currentAbortController = null;
            }
            try {
                await fetch("/proxy_cancel", {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ session_id: currentSessionId })
                });
            } catch(e) { /* ignore */ }
        }

        // ===== TTS 朗读功能 =====
        let currentTtsAudio = null;
        let currentTtsBtn = null;

        function stripMarkdownForTTS(md) {
            // 移除代码块（含内容）
            let text = md.replace(/```[\\s\\S]*?```/g, '('+t('code_omitted')+')');
            // 移除行内代码
            text = text.replace(/`[^`]+`/g, '');
            // 移除图片
            text = text.replace(/!\\[.*?\\]\\(.*?\\)/g, '');
            // 移除链接，保留文字
            text = text.replace(/\\[([^\\]]+)\\]\\(.*?\\)/g, '$1');
            // 移除标题标记
            text = text.replace(/^#{1,6}\\s+/gm, '');
            // 移除粗体/斜体标记
            text = text.replace(/\\*{1,3}([^*]+)\\*{1,3}/g, '$1');
            // 移除工具调用提示行
            text = text.replace(/.*🔧.*调用工具.*\\n?/g, '');
            text = text.replace(/.*✅.*工具执行完成.*\\n?/g, '');
            // 清理多余空行
            text = text.replace(/\\n{3,}/g, '\\n\\n').trim();
            return text;
        }

        function stopTtsPlayback() {
            if (currentTtsAudio) {
                currentTtsAudio.pause();
                currentTtsAudio.src = '';
                currentTtsAudio = null;
            }
            if (currentTtsBtn) {
                currentTtsBtn.classList.remove('playing', 'loading');
                currentTtsBtn.querySelector('.tts-label').textContent = t('tts_read');
                currentTtsBtn = null;
            }
        }

        async function handleTTS(btn, text) {
            // 如果点击的是正在播放的按钮，则停止
            if (btn === currentTtsBtn && currentTtsAudio) {
                stopTtsPlayback();
                return;
            }
            // 停止上一个播放
            stopTtsPlayback();

            const cleanText = stripMarkdownForTTS(text);
            if (!cleanText) return;

            currentTtsBtn = btn;
            btn.classList.add('loading');
            btn.querySelector('.tts-label').textContent = t('tts_loading');

            try {
                const resp = await fetch('/proxy_tts', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: cleanText })
                });
                if (!resp.ok) throw new Error(t('tts_request_failed'));

                const blob = await resp.blob();
                const url = URL.createObjectURL(blob);
                const audio = new Audio(url);
                currentTtsAudio = audio;

                btn.classList.remove('loading');
                btn.classList.add('playing');
                btn.querySelector('.tts-label').textContent = t('tts_stop');

                audio.onended = () => {
                    URL.revokeObjectURL(url);
                    stopTtsPlayback();
                };
                audio.onerror = () => {
                    URL.revokeObjectURL(url);
                    stopTtsPlayback();
                };
                audio.play();
            } catch (e) {
                console.error('TTS error:', e);
                stopTtsPlayback();
            }
        }

        function createTtsButton(textRef) {
            const btn = document.createElement('div');
            btn.className = 'tts-btn';
            btn.innerHTML = `
                <span class="tts-spinner"></span>
                <svg class="tts-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
                    <path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path>
                    <path d="M19.07 4.93a10 10 0 0 1 0 14.14"></path>
                </svg>
                <span class="tts-label">${t('tts_read')}</span>`;
            btn.onclick = () => handleTTS(btn, textRef());
            return btn;
        }

        function appendMessage(content, isUser = false, images = [], fileNames = [], audioNames = []) {
            const wrapper = document.createElement('div');
            wrapper.className = `flex ${isUser ? 'justify-end' : 'justify-start'} animate-in fade-in duration-300`;
            const div = document.createElement('div');
            div.className = `p-4 max-w-[85%] shadow-sm ${isUser ? 'bg-blue-600 text-white message-user' : 'bg-white border text-gray-800 message-agent'}`;
            if (isUser) {
                let extraHtml = '';
                if (images && images.length > 0) {
                    extraHtml += images.map(src => `<img src="${src}" class="chat-inline-image">`).join('');
                }
                if (fileNames && fileNames.length > 0) {
                    extraHtml += fileNames.map(n => `<div class="chat-file-tag">📄 ${escapeHtml(n)}</div>`).join('');
                }
                if (audioNames && audioNames.length > 0) {
                    extraHtml += audioNames.map(n => `<div class="chat-audio-tag">🎤 ${escapeHtml(n)}</div>`).join('');
                }
                if (extraHtml) {
                    div.innerHTML = extraHtml + '<div style="margin-top:6px">' + escapeHtml(content) + '</div>';
                } else {
                    div.innerText = content;
                }
            } else {
                div.className += " markdown-body";
                div.innerHTML = marked.parse(content);
                div.querySelectorAll('pre code').forEach((block) => hljs.highlightElement(block));
                // AI 消息添加朗读按钮（content 非空时）
                if (content) {
                    const ttsBtn = createTtsButton(() => div.innerText || div.textContent || '');
                    div.appendChild(ttsBtn);
                }
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
            if (!text && pendingImages.length === 0 && pendingFiles.length === 0 && pendingAudios.length === 0) return;
            if (sendBtn.disabled) return;

            // Stop recording if active
            if (isRecording) stopRecording();

            // Capture images, files, audios before clearing
            const imagesToSend = pendingImages.map(img => img.base64);
            const imagePreviewSrcs = [...imagesToSend];
            const filesToSend = pendingFiles.map(f => ({ name: f.name, content: f.content, type: f.type }));
            const fileNames = pendingFiles.map(f => f.name);
            const audiosToSend = pendingAudios.map(a => ({ base64: a.base64, name: a.name, format: a.format }));
            const audioNames = pendingAudios.map(a => a.name);

            const label = text || (imagePreviewSrcs.length ? '('+t('image_placeholder')+')' : audioNames.length ? '('+t('audio_placeholder')+')' : '('+t('file_placeholder')+')');
            appendMessage(label, true, imagePreviewSrcs, fileNames, audioNames);
            inputField.value = '';
            inputField.style.height = 'auto';
            pendingImages = [];
            pendingFiles = [];
            pendingAudios = [];
            renderImagePreviews();
            renderFilePreviews();
            renderAudioPreviews();
            sendBtn.disabled = true;
            showTyping();

            currentAbortController = new AbortController();
            setStreamingUI(true);

            let agentDiv = null;
            let fullText = '';

            try {
                // --- 构造 OpenAI 格式的 content parts ---
                const contentParts = [];
                if (text) {
                    contentParts.push({ type: 'text', text: text });
                }
                // 图片 → image_url
                for (const img of imagesToSend) {
                    contentParts.push({ type: 'image_url', image_url: { url: img } });
                }
                // 音频 → input_audio
                for (const audio of audiosToSend) {
                    contentParts.push({
                        type: 'input_audio',
                        input_audio: { data: audio.base64, format: audio.format || 'webm' }
                    });
                }
                // 文件 → file
                for (const f of filesToSend) {
                    const fileData = f.content.startsWith('data:') ? f.content : 'data:application/octet-stream;base64,' + f.content;
                    contentParts.push({
                        type: 'file',
                        file: { filename: f.name, file_data: fileData }
                    });
                }

                // 如果只有纯文本，content 用字符串；否则用 parts 数组
                let msgContent;
                if (contentParts.length === 1 && contentParts[0].type === 'text') {
                    msgContent = contentParts[0].text;
                } else if (contentParts.length > 0) {
                    msgContent = contentParts;
                } else {
                    msgContent = '(空消息)';
                }

                // --- 构造 OpenAI /v1/chat/completions 请求 ---
                const openaiPayload = {
                    model: 'mini-timebot',
                    messages: [{ role: 'user', content: msgContent }],
                    stream: true,
                    session_id: currentSessionId,
                    enabled_tools: getEnabledTools(),
                };

                const response = await fetch("/v1/chat/completions", {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + getAuthToken()
                    },
                    body: JSON.stringify(openaiPayload),
                    signal: currentAbortController.signal
                });

                const typingIndicator = document.getElementById('typing-indicator');
                if (typingIndicator) typingIndicator.remove();

                if (response.status === 401) {
                    appendMessage(t('login_expired'), false);
                    handleLogout();
                    return;
                }
                if (!response.ok) throw new Error("Agent error");

                agentDiv = appendMessage('', false);

                // --- 解析 OpenAI SSE 流式响应 ---
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\\n');
                    buffer = lines.pop();

                    for (const line of lines) {
                        if (!line.startsWith('data: ')) continue;
                        const data = line.slice(6).trim();
                        if (data === '[DONE]') continue;

                        try {
                            const chunk = JSON.parse(data);
                            const delta = chunk.choices && chunk.choices[0] && chunk.choices[0].delta;
                            if (delta && delta.content) {
                                fullText += delta.content;
                                agentDiv.innerHTML = marked.parse(fullText);
                                agentDiv.querySelectorAll('pre code').forEach((block) => {
                                    if (!block.dataset.highlighted) {
                                        hljs.highlightElement(block);
                                        block.dataset.highlighted = 'true';
                                    }
                                });
                                chatBox.scrollTop = chatBox.scrollHeight;
                            }
                        } catch(e) {
                            // 跳过无法解析的 chunk
                        }
                    }
                }

                if (fullText) {
                    agentDiv.innerHTML = marked.parse(fullText);
                    agentDiv.querySelectorAll('pre code').forEach((block) => hljs.highlightElement(block));
                    // 流式结束后添加朗读按钮
                    const ttsBtn = createTtsButton(() => agentDiv.innerText || agentDiv.textContent || '');
                    agentDiv.appendChild(ttsBtn);
                    chatBox.scrollTop = chatBox.scrollHeight;
                }

                if (!fullText) {
                    agentDiv.innerHTML = `<span class="text-gray-400">${t('no_response')}</span>`;
                }

                // After agent response, refresh OASIS topics (in case a new discussion was started)
                setTimeout(() => refreshOasisTopics(), 1000);

            } catch (error) {
                const typingIndicator = document.getElementById('typing-indicator');
                if (typingIndicator) typingIndicator.remove();
                if (error.name === 'AbortError') {
                    if (agentDiv) {
                        fullText += '\\n\\n' + t('thinking_stopped');
                        agentDiv.innerHTML = marked.parse(fullText);
                    } else {
                        appendMessage(t('thinking_stopped'), false);
                    }
                } else {
                    appendMessage(t('agent_error') + ': ' + error.message, false);
                }
            } finally {
                currentAbortController = null;
                setStreamingUI(false);
            }
        }

        inputField.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = (this.scrollHeight) + 'px';
        });
        inputField.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
        });
        inputField.addEventListener('paste', handlePasteImage);

        // ================================================================
        // ===== OASIS 讨论面板逻辑 =====
        // ================================================================

        let oasisPanelOpen = false;
        let oasisCurrentTopicId = null;
        let oasisPollingTimer = null;
        let oasisStreamReader = null;

        // Expert avatar mapping
        const expertAvatars = {
            [t('oasis_expert_creative')]: { cls: 'expert-creative', icon: '💡' },
            [t('oasis_expert_critical')]: { cls: 'expert-critical', icon: '🔍' },
            [t('oasis_expert_data')]: { cls: 'expert-data', icon: '📊' },
            [t('oasis_expert_synthesis')]: { cls: 'expert-synthesis', icon: '🎯' },
        };

        function getExpertAvatar(name) {
            return expertAvatars[name] || { cls: 'expert-default', icon: '🤖' };
        }

        function getStatusBadge(status) {
            const map = {
                'pending': { cls: 'oasis-status-pending', text: t('oasis_status_pending') },
                'discussing': { cls: 'oasis-status-discussing', text: t('oasis_status_discussing') },
                'concluded': { cls: 'oasis-status-concluded', text: t('oasis_status_concluded') },
                'error': { cls: 'oasis-status-error', text: t('oasis_status_error') },
                'cancelled': { cls: 'oasis-status-error', text: t('oasis_status_cancelled') },
            };
            return map[status] || { cls: 'oasis-status-pending', text: status };
        }

        function formatTime(ts) {
            const d = new Date(ts * 1000);
            return d.toLocaleTimeString(currentLang === 'zh-CN' ? 'zh-CN' : 'en-US', { hour: '2-digit', minute: '2-digit' });
        }

        function toggleOasisPanel() {
            const panel = document.getElementById('oasis-panel');
            oasisPanelOpen = !oasisPanelOpen;
            if (oasisPanelOpen) {
                panel.classList.remove('collapsed-panel');
                panel.classList.remove('mobile-open');
                refreshOasisTopics();
            } else {
                panel.classList.add('collapsed-panel');
                panel.classList.remove('mobile-open');
                stopOasisPolling();
            }
        }

        function toggleOasisMobile() {
            const panel = document.getElementById('oasis-panel');
            if (panel.classList.contains('mobile-open')) {
                panel.classList.remove('mobile-open');
                stopOasisPolling();
            } else {
                panel.classList.remove('collapsed-panel');
                panel.classList.add('mobile-open');
                refreshOasisTopics();
            }
        }

        function toggleMobileMenu() {
            const dd = document.getElementById('mobile-menu-dropdown');
            if (dd.style.display === 'none') {
                dd.style.display = 'block';
                // close when tapping outside
                setTimeout(() => document.addEventListener('click', closeMobileMenuOutside, { once: true }), 0);
            } else {
                dd.style.display = 'none';
            }
        }
        function closeMobileMenu() {
            document.getElementById('mobile-menu-dropdown').style.display = 'none';
        }
        function closeMobileMenuOutside(e) {
            const wrapper = document.querySelector('.mobile-menu-wrapper');
            if (!wrapper.contains(e.target)) closeMobileMenu();
        }

        function stopOasisPolling() {
            if (oasisPollingTimer) {
                clearInterval(oasisPollingTimer);
                oasisPollingTimer = null;
            }
            if (oasisStreamReader) {
                oasisStreamReader.cancel();
                oasisStreamReader = null;
            }
        }

        async function refreshOasisTopics() {
            try {
                const resp = await fetch('/proxy_oasis/topics');
                console.log('[OASIS] Topics response status:', resp.status);
                if (!resp.ok) {
                    console.error('[OASIS] Failed to fetch topics:', resp.status);
                    return;
                }
                const topics = await resp.json();
                console.log('[OASIS] Topics data:', topics);
                renderTopicList(topics);
            } catch (e) {
                console.error('[OASIS] Failed to load topics:', e);
            }
        }

        function renderTopicList(topics) {
            const container = document.getElementById('oasis-topic-list');
            const countEl = document.getElementById('oasis-topic-count');
            countEl.textContent = topics.length + ' ' + t('oasis_topics_count');

            if (topics.length === 0) {
                container.innerHTML = `
                    <div class="p-6 text-center text-gray-400 text-sm">
                        <div class="text-3xl mb-2">🏛️</div>
                        <p>${t('oasis_no_topics')}</p>
                        <p class="text-xs mt-1">${t('oasis_start_hint')}</p>
                    </div>`;
                return;
            }

            // Sort: discussing first, then by created_at desc
            topics.sort((a, b) => {
                if (a.status === 'discussing' && b.status !== 'discussing') return -1;
                if (b.status === 'discussing' && a.status !== 'discussing') return 1;
                return (b.created_at || 0) - (a.created_at || 0);
            });

            container.innerHTML = topics.map(topic => {
                const badge = getStatusBadge(topic.status);
                const isActive = topic.topic_id === oasisCurrentTopicId;
                const isRunning = topic.status === 'discussing' || topic.status === 'pending';
                return `
                    <div class="oasis-topic-item p-3 border-b ${isActive ? 'active' : ''}" onclick="openOasisTopic('${topic.topic_id}')">
                        <div class="flex items-center justify-between mb-1">
                            <span class="oasis-status-badge ${badge.cls}">${badge.text}</span>
                            <div class="flex items-center space-x-1">
                                ${isRunning ? `<button onclick="event.stopPropagation(); cancelOasisTopic('${topic.topic_id}')" class="oasis-action-btn oasis-btn-cancel" title="${t('oasis_cancel')}">⏹</button>` : ''}
                                <button onclick="event.stopPropagation(); deleteOasisTopic('${topic.topic_id}')" class="oasis-action-btn oasis-btn-delete" title="${t('oasis_delete')}">🗑</button>
                                <span class="text-[10px] text-gray-400">${topic.created_at ? formatTime(topic.created_at) : ''}</span>
                            </div>
                        </div>
                        <p class="text-sm text-gray-800 font-medium line-clamp-2">${escapeHtml(topic.question)}</p>
                        <div class="flex items-center space-x-3 mt-1 text-[10px] text-gray-400">
                            <span>💬 ${topic.post_count || 0} ${t('oasis_posts')}</span>
                            <span>🔄 ${topic.current_round}/${topic.max_rounds} ${t('oasis_round')}</span>
                        </div>
                    </div>`;
            }).join('');
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        async function openOasisTopic(topicId) {
            oasisCurrentTopicId = topicId;
            stopOasisPolling();

            // Switch to detail view
            document.getElementById('oasis-topic-list-view').style.display = 'none';
            document.getElementById('oasis-detail-view').style.display = 'flex';

            // Load topic detail
            await loadTopicDetail(topicId);
        }

        function showOasisTopicList() {
            stopOasisPolling();
            oasisCurrentTopicId = null;
            document.getElementById('oasis-detail-view').style.display = 'none';
            document.getElementById('oasis-topic-list-view').style.display = 'flex';
            refreshOasisTopics();
        }

        async function loadTopicDetail(topicId) {
            try {
                const resp = await fetch(`/proxy_oasis/topics/${topicId}`);
                console.log('[OASIS] Detail response status:', resp.status);
                if (!resp.ok) {
                    console.error('[OASIS] Failed to fetch detail:', resp.status);
                    return;
                }
                const detail = await resp.json();
                console.log('[OASIS] Detail data:', detail);
                console.log('[OASIS] Posts count:', (detail.posts || []).length);
                renderTopicDetail(detail);

                // If still discussing, start polling for updates
                if (detail.status === 'discussing' || detail.status === 'pending') {
                    startDetailPolling(topicId);
                }
            } catch (e) {
                console.warn('Failed to load topic detail:', e);
            }
        }

        function renderTopicDetail(detail) {
            const badge = getStatusBadge(detail.status);
            document.getElementById('oasis-detail-status').className = 'oasis-status-badge ' + badge.cls;
            document.getElementById('oasis-detail-status').textContent = badge.text;
            const roundText = currentLang === 'zh-CN' ? `第 ${detail.current_round}/${detail.max_rounds} ${t('oasis_round')}` : `Round ${detail.current_round}/${detail.max_rounds}`;
            document.getElementById('oasis-detail-round').textContent = roundText;
            document.getElementById('oasis-detail-question').textContent = detail.question;

            // Render action buttons in detail header
            const actionsEl = document.getElementById('oasis-detail-actions');
            const isRunning = detail.status === 'discussing' || detail.status === 'pending';
            let btns = '';
            if (isRunning) {
                btns += `<button onclick="cancelOasisTopic('${detail.topic_id}')" class="oasis-detail-action-btn cancel">⏹ ${t('oasis_cancel')}</button>`;
            }
            btns += `<button onclick="deleteOasisTopic('${detail.topic_id}')" class="oasis-detail-action-btn delete">🗑 ${t('oasis_delete')}</button>`;
            actionsEl.innerHTML = btns;

            renderPosts(detail.posts || []);

            // Show/hide conclusion
            const conclusionArea = document.getElementById('oasis-conclusion-area');
            if (detail.conclusion && detail.status === 'concluded') {
                document.getElementById('oasis-conclusion-text').textContent = detail.conclusion;
                conclusionArea.style.display = 'block';
            } else {
                conclusionArea.style.display = 'none';
            }
        }

        function renderPosts(posts) {
            const box = document.getElementById('oasis-posts-box');

            if (posts.length === 0) {
                box.innerHTML = `
                    <div class="text-center text-gray-400 text-sm py-8">
                        <div class="text-2xl mb-2">💭</div>
                        <p>${t('oasis_waiting')}</p>
                    </div>`;
                return;
            }

            box.innerHTML = posts.map(p => {
                const avatar = getExpertAvatar(p.author);
                const isReply = p.reply_to !== null && p.reply_to !== undefined;
                const totalVotes = p.upvotes + p.downvotes;
                const upPct = totalVotes > 0 ? (p.upvotes / totalVotes * 100) : 50;

                return `
                    <div class="oasis-post bg-white rounded-xl p-3 border shadow-sm ${isReply ? 'ml-4 border-l-2 border-l-blue-300' : ''}">
                        <div class="flex items-start space-x-2">
                            <div class="oasis-expert-avatar ${avatar.cls}" title="${escapeHtml(p.author)}">${avatar.icon}</div>
                            <div class="flex-1 min-w-0">
                                <div class="flex items-center justify-between">
                                    <span class="text-xs font-semibold text-gray-700">${escapeHtml(p.author)}</span>
                                    <div class="flex items-center space-x-2 text-[10px] text-gray-400">
                                        ${isReply ? '<span>↩️ #' + p.reply_to + '</span>' : ''}
                                        <span>#${p.id}</span>
                                    </div>
                                </div>
                                <p class="text-xs text-gray-600 mt-1 leading-relaxed">${escapeHtml(p.content)}</p>
                                <div class="flex items-center space-x-3 mt-2">
                                    <div class="flex items-center space-x-1">
                                        <span class="text-[10px]">👍 ${p.upvotes}</span>
                                        <span class="text-[10px]">👎 ${p.downvotes}</span>
                                    </div>
                                    ${totalVotes > 0 ? `
                                        <div class="flex-1 oasis-vote-bar flex">
                                            <div class="oasis-vote-up" style="width: ${upPct}%"></div>
                                            <div class="oasis-vote-down" style="width: ${100 - upPct}%"></div>
                                        </div>` : ''}
                                </div>
                            </div>
                        </div>
                    </div>`;
            }).join('');

            // Auto-scroll to bottom
            box.scrollTop = box.scrollHeight;
        }

        function startDetailPolling(topicId) {
            stopOasisPolling();
            let lastPostCount = 0;
            let errorCount = 0;
            oasisPollingTimer = setInterval(async () => {
                if (oasisCurrentTopicId !== topicId) {
                    stopOasisPolling();
                    return;
                }
                try {
                    const resp = await fetch(`/proxy_oasis/topics/${topicId}`);
                    if (!resp.ok) {
                        errorCount++;
                        console.warn(`OASIS polling error: HTTP ${resp.status}`);
                        if (errorCount >= 5) {
                            console.error('OASIS polling failed 5 times, stopping');
                            stopOasisPolling();
                        }
                        return;
                    }
                    errorCount = 0;
                    const detail = await resp.json();
                    
                    // Only re-render if posts changed
                    const currentPostCount = (detail.posts || []).length;
                    if (currentPostCount !== lastPostCount || detail.status !== 'discussing') {
                        renderTopicDetail(detail);
                        lastPostCount = currentPostCount;
                    }

                    // Stop polling when discussion ends
                    if (detail.status === 'concluded' || detail.status === 'error') {
                        stopOasisPolling();
                        refreshOasisTopics();
                    }
                } catch (e) {
                    errorCount++;
                    console.warn('OASIS polling error:', e);
                }
            }, 1500); // Poll every 1.5 seconds for faster updates
        }

        async function cancelOasisTopic(topicId) {
            if (!confirm(t('oasis_cancel_confirm'))) return;
            try {
                const resp = await fetch(`/proxy_oasis/topics/${topicId}/cancel`, { method: 'POST' });
                const data = await resp.json();
                if (resp.ok) {
                    stopOasisPolling();
                    if (oasisCurrentTopicId === topicId) {
                        await loadTopicDetail(topicId);
                    }
                    refreshOasisTopics();
                } else {
                    alert(t('oasis_action_fail') + ': ' + (data.error || data.detail || data.message || ''));
                }
            } catch (e) {
                alert(t('oasis_action_fail') + ': ' + e.message);
            }
        }

        async function deleteOasisTopic(topicId) {
            if (!confirm(t('oasis_delete_confirm'))) return;
            try {
                const resp = await fetch(`/proxy_oasis/topics/${topicId}/purge`, { method: 'POST' });
                const data = await resp.json();
                if (resp.ok) {
                    stopOasisPolling();
                    if (oasisCurrentTopicId === topicId) {
                        showOasisTopicList();
                    } else {
                        refreshOasisTopics();
                    }
                } else {
                    alert(t('oasis_action_fail') + ': ' + (data.error || data.detail || data.message || ''));
                }
            } catch (e) {
                alert(t('oasis_action_fail') + ': ' + e.message);
            }
        }

        async function deleteAllOasisTopics() {
            const countEl = document.getElementById('oasis-topic-count');
            const count = parseInt(countEl.textContent) || 0;
            if (count === 0) {
                alert(t('oasis_no_topics') || '暂无讨论话题');
                return;
            }
            const confirmMsg = (currentLang === 'zh-CN')
                ? `确定要清空所有 ${count} 个讨论话题吗？此操作不可恢复！`
                : `Delete all ${count} topics? This cannot be undone!`;
            if (!confirm(confirmMsg)) return;

            try {
                const resp = await fetch('/proxy_oasis/topics', { method: 'DELETE' });
                const data = await resp.json();
                if (resp.ok) {
                    stopOasisPolling();
                    showOasisTopicList();
                    alert((currentLang === 'zh-CN' ? '已删除 ' : 'Deleted ') + data.deleted_count + (currentLang === 'zh-CN' ? ' 个话题' : ' topics'));
                } else {
                    alert(t('oasis_action_fail') + ': ' + (data.error || data.detail || data.message || ''));
                }
            } catch (e) {
                alert(t('oasis_action_fail') + ': ' + e.message);
            }
        }

        // Auto-refresh topic list periodically when panel is open
        setInterval(() => {
            if (oasisPanelOpen && !oasisCurrentTopicId && currentUserId) {
                refreshOasisTopics();
            }
        }, 10000); // Every 10 seconds

        // === System trigger polling: 检测后台系统触发产生的新消息 ===
        let _sessionStatusTimer = null;

        function startSessionStatusPolling() {
            stopSessionStatusPolling();
            _sessionStatusTimer = setInterval(async () => {
                if (!currentUserId || !currentSessionId) return;
                // 用户正在流式对话中，跳过轮询
                if (cancelBtn.style.display !== 'none') return;
                try {
                    const resp = await fetch('/proxy_session_status', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ session_id: currentSessionId })
                    });
                    const data = await resp.json();
                    if (data.has_new_messages) {
                        // 有系统触发的新消息，自动刷新历史
                        console.log('[SessionStatus] New system messages detected, refreshing...');
                        switchToSession(currentSessionId);
                    }
                } catch(e) {
                    // 静默忽略
                }
            }, 5000); // 每 5 秒轮询一次
        }

        function stopSessionStatusPolling() {
            if (_sessionStatusTimer) {
                clearInterval(_sessionStatusTimer);
                _sessionStatusTimer = null;
            }
        }

        // 登录成功后启动轮询
        const _origLogin = typeof handleLogin === 'function' ? null : null;
        // 监听 chat-container 可见性来启动/停止轮询
        const _chatObserver = new MutationObserver(() => {
            const chatContainer = document.getElementById('chat-container');
            if (chatContainer && chatContainer.style.display !== 'none') {
                startSessionStatusPolling();
            } else {
                stopSessionStatusPolling();
            }
        });
        _chatObserver.observe(document.body, { childList: true, subtree: true, attributes: true });

        // ================================================================
        // ===== Group Chat (群聊) 逻辑 =====
        // ================================================================

        // Agent 颜色方案：根据名字 hash 分配一致的颜色
        const _agentColorPalette = [
            { bg: '#f0fdf4', border: '#bbf7d0', text: '#166534', sender: '#15803d', pre: '#1a2e1a', code: '#d1fae5' },
            { bg: '#eff6ff', border: '#bfdbfe', text: '#1e40af', sender: '#2563eb', pre: '#1e2a4a', code: '#dbeafe' },
            { bg: '#fdf4ff', border: '#e9d5ff', text: '#6b21a8', sender: '#7c3aed', pre: '#2d1a3e', code: '#ede9fe' },
            { bg: '#fff7ed', border: '#fed7aa', text: '#9a3412', sender: '#ea580c', pre: '#3b1a0a', code: '#ffedd5' },
            { bg: '#fef2f2', border: '#fecaca', text: '#991b1b', sender: '#dc2626', pre: '#3b1212', code: '#fee2e2' },
            { bg: '#f0fdfa', border: '#99f6e4', text: '#115e59', sender: '#0d9488', pre: '#0f2d2a', code: '#ccfbf1' },
            { bg: '#fefce8', border: '#fde68a', text: '#854d0e', sender: '#ca8a04', pre: '#2d2305', code: '#fef9c3' },
            { bg: '#fdf2f8', border: '#fbcfe8', text: '#9d174d', sender: '#db2777', pre: '#3b0d24', code: '#fce7f3' },
        ];
        const _agentColorCache = {};
        function getAgentColor(sender) {
            if (_agentColorCache[sender]) return _agentColorCache[sender];
            let hash = 0;
            for (let i = 0; i < sender.length; i++) {
                hash = ((hash << 5) - hash) + sender.charCodeAt(i);
                hash |= 0;
            }
            const color = _agentColorPalette[Math.abs(hash) % _agentColorPalette.length];
            _agentColorCache[sender] = color;
            return color;
        }
        function applyAgentColor(el, sender) {
            const c = getAgentColor(sender);
            const content = el.querySelector('.group-msg-content');
            const senderEl = el.querySelector('.group-msg-sender');
            if (content) {
                content.style.background = c.bg;
                content.style.borderColor = c.border;
                content.style.color = c.text;
            }
            if (senderEl) senderEl.style.color = c.sender;
            el.querySelectorAll('.group-msg-content pre').forEach(pre => { pre.style.background = c.pre; });
            el.querySelectorAll('.group-msg-content code').forEach(code => { code.style.color = c.code; });
        }

        let currentPage = 'chat'; // 'chat' or 'group'
        let currentGroupId = null;
        let groupPollingTimer = null;
        let groupLastMsgId = 0;

        function switchPage(page) {
            currentPage = page;
            // Update tabs
            document.getElementById('tab-chat').classList.toggle('active', page === 'chat');
            document.getElementById('tab-group').classList.toggle('active', page === 'group');
            // Show/hide pages
            const chatPage = document.getElementById('page-chat');
            const groupPage = document.getElementById('page-group');
            if (page === 'chat') {
                chatPage.classList.remove('hidden-page');
                chatPage.style.display = 'flex';
                groupPage.classList.remove('active');
                stopGroupPolling();
            } else {
                chatPage.classList.add('hidden-page');
                chatPage.style.display = 'none';
                groupPage.classList.add('active');
                loadGroupList();
            }
        }

        function stopGroupPolling() {
            if (groupPollingTimer) { clearInterval(groupPollingTimer); groupPollingTimer = null; }
        }

        async function loadGroupList() {
            try {
                const resp = await fetch('/proxy_groups', {
                    headers: { 'Authorization': 'Bearer ' + getAuthToken() }
                });
                if (!resp.ok) return;
                const groups = await resp.json();
                renderGroupList(groups);
            } catch (e) {
                console.error('Failed to load groups:', e);
            }
        }

        function renderGroupList(groups) {
            const container = document.getElementById('group-list');
            if (!groups || groups.length === 0) {
                container.innerHTML = `
                    <div class="group-empty-state" style="padding:40px 0;">
                        <div class="empty-icon">👥</div>
                        <div class="empty-text">${t('group_no_groups')}</div>
                    </div>`;
                return;
            }
            container.innerHTML = groups.map(g => {
                const isActive = g.group_id === currentGroupId;
                return `
                    <div class="group-item ${isActive ? 'active' : ''}" onclick="openGroup('${g.group_id}')">
                        <div class="group-name">${escapeHtml(g.name)}</div>
                        <div class="group-meta">${g.member_count || 0} ${t('group_member_count')} · ${g.message_count || 0} ${t('group_msg_count')}</div>
                        <button class="group-delete-btn" onclick="event.stopPropagation(); deleteGroup('${g.group_id}')">${t('delete_session')}</button>
                    </div>`;
            }).join('');
        }

        async function openGroup(groupId) {
            currentGroupId = groupId;
            groupLastMsgId = 0;
            stopGroupPolling();

            document.getElementById('group-empty-placeholder').style.display = 'none';
            const activeChat = document.getElementById('group-active-chat');
            activeChat.style.display = 'flex';

            // Load group detail
            try {
                const resp = await fetch(`/proxy_groups/${groupId}`, {
                    headers: { 'Authorization': 'Bearer ' + getAuthToken() }
                });
                if (!resp.ok) return;
                const detail = await resp.json();

                document.getElementById('group-active-name').textContent = detail.name;
                document.getElementById('group-active-id').textContent = '#' + groupId.slice(-8);

                renderGroupMessages(detail.messages || []);
                renderGroupMembers(detail.members || []);

                // Track last message ID
                if (detail.messages && detail.messages.length > 0) {
                    groupLastMsgId = detail.messages[detail.messages.length - 1].id;
                }

                // Start polling for new messages
                startGroupPolling(groupId);

                // Update group list selection
                loadGroupList();
            } catch (e) {
                console.error('Failed to open group:', e);
            }
        }

        function renderGroupMessages(messages) {
            const box = document.getElementById('group-messages-box');
            if (messages.length === 0) {
                box.innerHTML = '<div style="text-align:center;color:#9ca3af;padding:40px 0;font-size:13px;">暂无消息</div>';
                return;
            }
            box.innerHTML = messages.map(m => {
                const isSelf = m.sender === currentUserId || m.sender === currentUserId;
                const isAgent = !isSelf && m.sender_session;
                const msgClass = isSelf ? 'self' : (isAgent ? 'agent' : 'other');
                const timeStr = new Date(m.timestamp * 1000).toLocaleTimeString(currentLang === 'zh-CN' ? 'zh-CN' : 'en-US', {hour:'2-digit',minute:'2-digit'});
                return `
                    <div class="group-msg ${msgClass}" ${isAgent ? 'data-agent-sender="'+escapeHtml(m.sender)+'"' : ''}>
                        <div class="group-msg-sender">${escapeHtml(m.sender)}</div>
                        <div class="group-msg-content markdown-body">${marked.parse(m.content || '')}</div>
                        <div class="group-msg-time">${timeStr}</div>
                    </div>`;
            }).join('');
            box.querySelectorAll('pre code').forEach((block) => hljs.highlightElement(block));
            box.querySelectorAll('.group-msg.agent[data-agent-sender]').forEach(el => applyAgentColor(el, el.dataset.agentSender));
            box.scrollTop = box.scrollHeight;
        }

        function appendGroupMessages(messages) {
            const box = document.getElementById('group-messages-box');
            // Remove "no messages" placeholder if present
            const placeholder = box.querySelector('div[style*="text-align:center"]');
            if (placeholder && messages.length > 0) placeholder.remove();

            for (const m of messages) {
                const isSelf = m.sender === currentUserId || m.sender === currentUserId;
                const isAgent = !isSelf && m.sender_session;
                const msgClass = isSelf ? 'self' : (isAgent ? 'agent' : 'other');
                const timeStr = new Date(m.timestamp * 1000).toLocaleTimeString(currentLang === 'zh-CN' ? 'zh-CN' : 'en-US', {hour:'2-digit',minute:'2-digit'});
                const div = document.createElement('div');
                div.className = `group-msg ${msgClass}`;
                div.innerHTML = `
                    <div class="group-msg-sender">${escapeHtml(m.sender)}</div>
                    <div class="group-msg-content markdown-body">${marked.parse(m.content || '')}</div>
                    <div class="group-msg-time">${timeStr}</div>`;
                div.querySelectorAll('pre code').forEach((block) => hljs.highlightElement(block));
                if (isAgent) applyAgentColor(div, m.sender);
                box.appendChild(div);
                if (m.id > groupLastMsgId) groupLastMsgId = m.id;
            }
            box.scrollTop = box.scrollHeight;
        }

        function startGroupPolling(groupId) {
            stopGroupPolling();
            groupPollingTimer = setInterval(async () => {
                if (currentGroupId !== groupId || currentPage !== 'group') {
                    stopGroupPolling();
                    return;
                }
                try {
                    const resp = await fetch(`/proxy_groups/${groupId}/messages?after_id=${groupLastMsgId}`, {
                        headers: { 'Authorization': 'Bearer ' + getAuthToken() }
                    });
                    if (!resp.ok) return;
                    const data = await resp.json();
                    if (data.messages && data.messages.length > 0) {
                        appendGroupMessages(data.messages);
                    }
                } catch (e) {
                    // silent
                }
            }, 2000);
        }

        async function sendGroupMessage() {
            const input = document.getElementById('group-input');
            const text = input.value.trim();
            if (!text || !currentGroupId) return;
            input.value = '';

            try {
                await fetch(`/proxy_groups/${currentGroupId}/messages`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + getAuthToken()
                    },
                    body: JSON.stringify({ content: text })
                });
                // Immediately show in UI
                appendGroupMessages([{
                    id: groupLastMsgId + 1,
                    sender: currentUserId,
                    content: text,
                    timestamp: Date.now() / 1000
                }]);
                groupLastMsgId++;
            } catch (e) {
                console.error('Failed to send group message:', e);
            }
        }

        function renderGroupMembers(members) {
            const container = document.getElementById('group-current-members');
            container.innerHTML = members.map(m => {
                const badge = m.is_agent
                    ? `<span class="member-badge badge-agent">${t('group_agent')}</span>`
                    : `<span class="member-badge badge-owner">${t('group_owner')}</span>`;
                return `
                    <div class="member-item">
                        <span class="member-name">${escapeHtml(m.user_id)}${m.session_id !== 'default' ? '#' + m.session_id : ''}</span>
                        ${badge}
                    </div>`;
            }).join('');
        }

        let groupMemberPanelOpen = false;
        function toggleGroupMemberPanel() {
            groupMemberPanelOpen = !groupMemberPanelOpen;
            document.getElementById('group-member-panel').style.display = groupMemberPanelOpen ? 'flex' : 'none';
            if (groupMemberPanelOpen && currentGroupId) {
                loadAvailableSessions();
            }
        }

        async function loadAvailableSessions() {
            const container = document.getElementById('group-available-sessions');
            container.innerHTML = '<div class="text-xs text-gray-400 p-2">' + t('loading') + '</div>';
            try {
                const resp = await fetch(`/proxy_groups/${currentGroupId}/sessions`, {
                    headers: { 'Authorization': 'Bearer ' + getAuthToken() }
                });
                if (!resp.ok) return;
                const data = await resp.json();
                const sessions = data.sessions || [];

                // Get current members to mark them
                const detailResp = await fetch(`/proxy_groups/${currentGroupId}`, {
                    headers: { 'Authorization': 'Bearer ' + getAuthToken() }
                });
                const detail = await detailResp.json();
                const memberSet = new Set((detail.members || []).map(m => m.user_id + '#' + m.session_id));

                if (sessions.length === 0) {
                    container.innerHTML = '<div class="text-xs text-gray-400 p-2">' + t('group_no_sessions') + '</div>';
                    return;
                }

                container.innerHTML = sessions.map(s => {
                    const key = currentUserId + '#' + s.session_id;
                    const checked = memberSet.has(key) ? 'checked' : '';
                    const title = s.title || s.session_id;
                    return `
                        <label class="session-checkbox">
                            <input type="checkbox" ${checked} onchange="toggleGroupAgent('${s.session_id}', this.checked)">
                            <span class="session-label" title="${escapeHtml(title)}">${escapeHtml(title)}</span>
                        </label>`;
                }).join('');
            } catch (e) {
                container.innerHTML = '<div class="text-xs text-red-400 p-2">加载失败</div>';
            }
        }

        async function toggleGroupAgent(sessionId, add) {
            if (!currentGroupId) return;
            try {
                await fetch(`/proxy_groups/${currentGroupId}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + getAuthToken()
                    },
                    body: JSON.stringify({
                        members: [{
                            user_id: currentUserId,
                            session_id: sessionId,
                            action: add ? 'add' : 'remove'
                        }]
                    })
                });
                // Refresh member list
                const resp = await fetch(`/proxy_groups/${currentGroupId}`, {
                    headers: { 'Authorization': 'Bearer ' + getAuthToken() }
                });
                const detail = await resp.json();
                renderGroupMembers(detail.members || []);
            } catch (e) {
                console.error('Failed to toggle group agent:', e);
            }
        }

        function showCreateGroupModal() {
            const name = prompt(t('group_name_placeholder'));
            if (!name || !name.trim()) return;
            createGroup(name.trim());
        }

        async function createGroup(name) {
            try {
                const resp = await fetch('/proxy_groups', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + getAuthToken()
                    },
                    body: JSON.stringify({ name: name, members: [] })
                });
                if (!resp.ok) { alert('创建失败'); return; }
                const data = await resp.json();
                await loadGroupList();
                openGroup(data.group_id);
            } catch (e) {
                alert('创建失败: ' + e.message);
            }
        }

        async function deleteGroup(groupId) {
            if (!confirm(t('group_delete_confirm'))) return;
            try {
                await fetch(`/proxy_groups/${groupId}`, {
                    method: 'DELETE',
                    headers: { 'Authorization': 'Bearer ' + getAuthToken() }
                });
                if (currentGroupId === groupId) {
                    currentGroupId = null;
                    document.getElementById('group-active-chat').style.display = 'none';
                    document.getElementById('group-empty-placeholder').style.display = 'flex';
                    stopGroupPolling();
                }
                loadGroupList();
            } catch (e) {
                alert('删除失败: ' + e.message);
            }
        }
    </script>

    <script>
    // === Native App Enhancements ===

    // 1. Splash screen dismiss
    window.addEventListener('load', () => {
        setTimeout(() => {
            const splash = document.getElementById('app-splash');
            if (splash) {
                splash.classList.add('fade-out');
                setTimeout(() => splash.remove(), 600);
            }
        }, 800);
    });

    // 2. Prevent pull-to-refresh and overscroll bounce
    document.addEventListener('touchmove', function(e) {
        // Allow scrolling inside scrollable containers
        let el = e.target;
        while (el && el !== document.body) {
            const style = window.getComputedStyle(el);
            if ((style.overflowY === 'auto' || style.overflowY === 'scroll') && el.scrollHeight > el.clientHeight) {
                return; // Allow scroll inside this element
            }
            el = el.parentElement;
        }
        e.preventDefault();
    }, { passive: false });

    // 3. Prevent double-tap zoom
    let lastTouchEnd = 0;
    document.addEventListener('touchend', function(e) {
        const now = Date.now();
        if (now - lastTouchEnd <= 300) {
            e.preventDefault();
        }
        lastTouchEnd = now;
    }, false);

    // 4. Prevent pinch zoom
    document.addEventListener('gesturestart', function(e) {
        e.preventDefault();
    });
    document.addEventListener('gesturechange', function(e) {
        e.preventDefault();
    });

    // 5. Prevent context menu on long press - mobile only (except in chat messages)
    const isTouchDevice = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);
    if (isTouchDevice) {
        document.addEventListener('contextmenu', function(e) {
            const allowed = e.target.closest('.message-agent, .message-user, .markdown-body, textarea, input');
            if (!allowed) {
                e.preventDefault();
            }
        });
    }

    // 6. Online/Offline detection
    function updateOnlineStatus() {
        const banner = document.getElementById('offline-banner');
        if (navigator.onLine) {
            banner.classList.remove('show');
        } else {
            banner.classList.add('show');
        }
    }
    window.addEventListener('online', updateOnlineStatus);
    window.addEventListener('offline', updateOnlineStatus);

    // 7. Register Service Worker for PWA caching
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js').catch(() => {});
    }

    // 8. iOS standalone: handle navigation to stay in-app
    if (window.navigator.standalone) {
        document.addEventListener('click', function(e) {
            const a = e.target.closest('a');
            if (a && a.href && !a.target && a.hostname === location.hostname) {
                e.preventDefault();
                location.href = a.href;
            }
        });
    }

    // 9. Keyboard handling for mobile/PWA - comprehensive solution
    if (isTouchDevice && window.visualViewport) {
        const chatMain = document.querySelector('.chat-main');
        const chatContainer = document.querySelector('.chat-container');
        const header = document.querySelector('header');
        const inputArea = document.querySelector('.border-t.p-2');
        
        // PWA Standalone mode detection
        const isPWA = window.matchMedia('(display-mode: standalone)').matches || 
                      window.navigator.standalone === true;
        
        let lastHeight = window.visualViewport.height;
        
        function handleViewportChange() {
            const vh = window.visualViewport.height;
            const windowHeight = window.innerHeight;
            const keyboardHeight = windowHeight - vh;
            
            // Detect if keyboard is open (more than 100px difference)
            const keyboardOpen = keyboardHeight > 100;
            
            if (isPWA || keyboardOpen) {
                // PWA mode or keyboard open: adjust heights
                const availableHeight = vh;
                
                // Update CSS variable for app height
                document.documentElement.style.setProperty('--app-height', availableHeight + 'px');
                
                // Chat main takes full available height
                if (chatMain) {
                    chatMain.style.height = availableHeight + 'px';
                    chatMain.style.maxHeight = availableHeight + 'px';
                }
                
                // Ensure flex behavior
                if (header) header.style.flexShrink = '0';
                if (inputArea) inputArea.style.flexShrink = '0';
                
                // Chat container gets remaining space via flex
                if (chatContainer) {
                    chatContainer.style.flex = '1';
                    chatContainer.style.minHeight = '0';
                }
            } else {
                // Normal mode: reset to CSS defaults
                document.documentElement.style.removeProperty('--app-height');
                
                if (chatMain) {
                    chatMain.style.height = '';
                    chatMain.style.maxHeight = '';
                }
                
                if (header) header.style.flexShrink = '';
                if (inputArea) inputArea.style.flexShrink = '';
                
                if (chatContainer) {
                    chatContainer.style.flex = '';
                    chatContainer.style.minHeight = '';
                }
            }
            
            lastHeight = vh;
        }
        
        // Debounced resize handler
        let resizeTimeout;
        function debouncedHandleViewportChange() {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(handleViewportChange, 50);
        }
        
        // Initial call
        handleViewportChange();
        
        // Listen for viewport changes
        window.visualViewport.addEventListener('resize', debouncedHandleViewportChange);
        window.visualViewport.addEventListener('scroll', handleViewportChange);
        
        // Also listen for window resize (orientation change)
        window.addEventListener('resize', debouncedHandleViewportChange);
        window.addEventListener('orientationchange', () => {
            setTimeout(handleViewportChange, 100);
        });
    }
    
    // Input focus: scroll into view on mobile
    const inputEl = document.getElementById('user-input');
    if (inputEl && isTouchDevice) {
        inputEl.addEventListener('focus', () => {
            setTimeout(() => {
                // Scroll input into view
                inputEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                // Also trigger viewport check
                if (window.visualViewport) {
                    window.dispatchEvent(new Event('resize'));
                }
            }, 100);
        });
        
        // On blur: reset after keyboard closes
        inputEl.addEventListener('blur', () => {
            setTimeout(() => {
                if (window.visualViewport) {
                    window.dispatchEvent(new Event('resize'));
                }
            }, 200);
        });
    }
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/manifest.json")
def manifest():
    """Serve PWA manifest for iOS/Android Add-to-Home-Screen support."""
    manifest_data = {
        "name": "Xavier AnyControl",
        "short_name": "AnyControl",
        "description": "Xavier AI Agent - Intelligent Control Assistant",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#111827",
        "theme_color": "#111827",
        "lang": "zh-CN",
        "categories": ["productivity", "utilities"],
        "icons": [
            {
                "src": "https://img.icons8.com/fluency/192/robot-2.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable"
            },
            {
                "src": "https://img.icons8.com/fluency/512/robot-2.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable"
            }
        ]
    }
    return app.response_class(
        response=__import__("json").dumps(manifest_data),
        mimetype="application/manifest+json"
    )


@app.route("/sw.js")
def service_worker():
    """Serve Service Worker for PWA offline support and caching."""
    sw_code = """
// Xavier AnyControl Service Worker
const CACHE_NAME = 'anycontrol-v1';
const PRECACHE_URLS = ['/'];

self.addEventListener('install', event => {
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(PRECACHE_URLS))
    );
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        ).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', event => {
    // Network-first strategy for API calls, cache-first for static assets
    if (event.request.url.includes('/proxy_') || event.request.url.includes('/ask') || event.request.url.includes('/v1/')) {
        event.respondWith(
            fetch(event.request).catch(() => caches.match(event.request))
        );
    } else {
        event.respondWith(
            caches.match(event.request).then(cached => {
                const fetched = fetch(event.request).then(response => {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
                    return response;
                }).catch(() => cached);
                return cached || fetched;
            })
        );
    }
});
"""
    return app.response_class(
        response=sw_code,
        mimetype="application/javascript",
        headers={"Service-Worker-Allowed": "/"}
    )


@app.route("/v1/chat/completions", methods=["POST", "OPTIONS"])
def proxy_openai_completions():
    """OpenAI 兼容端点透传：前端直接发 OpenAI 格式，原样转发到后端"""
    if request.method == "OPTIONS":
        # CORS preflight
        resp = Response("", status=204)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return resp

    # 直接透传请求体和 Authorization header 到后端
    auth_header = request.headers.get("Authorization", "")
    try:
        r = requests.post(
            LOCAL_OPENAI_COMPLETIONS_URL,
            json=request.get_json(silent=True),
            headers={
                "Authorization": auth_header,
                "Content-Type": "application/json",
            },
            stream=True,
            timeout=120,
        )
        if r.status_code != 200:
            return Response(r.content, status=r.status_code, content_type=r.headers.get("content-type", "application/json"))

        # 判断是否是流式响应
        content_type = r.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            def generate():
                for chunk in r.iter_content(chunk_size=None):
                    if chunk:
                        yield chunk
            return Response(
                generate(),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        else:
            return Response(r.content, status=r.status_code, content_type=content_type)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/v1/models", methods=["GET"])
def proxy_openai_models():
    """透传 /v1/models"""
    try:
        r = requests.get(f"http://127.0.0.1:{PORT_AGENT}/v1/models", timeout=10)
        return Response(r.content, status=r.status_code, content_type=r.headers.get("content-type", "application/json"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/proxy_login", methods=["POST"])
def proxy_login():
    """代理登录请求到后端 Agent"""
    user_id = request.json.get("user_id", "")
    password = request.json.get("password", "")

    try:
        r = requests.post(LOCAL_LOGIN_URL, json={"user_id": user_id, "password": password}, timeout=10)
        if r.status_code == 200:
            # 登录成功，在 Flask session 中记录
            session["user_id"] = user_id
            session["password"] = password  # 需要传给后端每次验证
            return jsonify(r.json())
        else:
            return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/proxy_ask", methods=["POST"])
def proxy_ask():
    """[已弃用] 非流式代理，请改用 /v1/chat/completions (stream=false)"""
    user_id = session.get("user_id")
    password = session.get("password")
    if not user_id or not password:
        return jsonify({"error": "未登录"}), 401

    user_content = request.json.get("content")
    images = request.json.get("images")

    # 构造 content parts
    content_parts = []
    if user_content:
        content_parts.append({"type": "text", "text": user_content})
    if images:
        for img_data in images:
            content_parts.append({"type": "image_url", "image_url": {"url": img_data}})

    if len(content_parts) == 1 and content_parts[0]["type"] == "text":
        msg_content = content_parts[0]["text"]
    elif content_parts:
        msg_content = content_parts
    else:
        msg_content = "(空消息)"

    openai_payload = {
        "model": "mini-timebot",
        "messages": [{"role": "user", "content": msg_content}],
        "stream": False,
        "user": user_id,
        "password": password,
    }

    try:
        r = requests.post(
            LOCAL_OPENAI_COMPLETIONS_URL,
            json=openai_payload,
            headers={"Authorization": f"Bearer {user_id}:{password}"},
            timeout=120,
        )
        if r.status_code == 401:
            session.clear()
            return jsonify(r.json()), 401
        resp = r.json()
        # 从 OpenAI 格式提取 content 转为原格式
        content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
        return jsonify({"status": "success", "response": content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/proxy_ask_stream", methods=["POST"])
def proxy_ask_stream():
    """[已弃用] 流式代理，请改用 /v1/chat/completions (stream=true)"""
    user_id = session.get("user_id")
    password = session.get("password")
    if not user_id or not password:
        return jsonify({"error": "未登录"}), 401

    data = request.get_json(silent=True)
    if data is None:
        content_len = request.content_length or 0
        print(f"[proxy_ask_stream] ⚠️ JSON 解析失败, content_length={content_len}, content_type={request.content_type}")
        return jsonify({"error": f"请求体解析失败 (大小: {content_len/1024/1024:.1f}MB)"}), 400

    user_content = data.get("content")
    enabled_tools = data.get("enabled_tools")  # None or list
    session_id = data.get("session_id", "default")
    images = data.get("images")  # None or list of base64 strings
    files = data.get("files")    # None or list of {name, content}
    audios = data.get("audios")  # None or list of {base64, name, format}
    print(f"[proxy_ask_stream] 收到请求: text={bool(user_content)}, images={len(images) if images else 0}, files={len(files) if files else 0}, audios={len(audios) if audios else 0}")

    # 构造 OpenAI 格式的 messages content parts
    content_parts = []
    if user_content:
        content_parts.append({"type": "text", "text": user_content})

    # 图片 → image_url parts
    if images:
        for img_data in images:
            content_parts.append({"type": "image_url", "image_url": {"url": img_data}})

    # 音频 → input_audio parts
    if audios:
        for audio in audios:
            content_parts.append({
                "type": "input_audio",
                "input_audio": {
                    "data": audio.get("base64", ""),
                    "format": audio.get("format", "webm"),
                },
            })

    # 文件 → file parts
    if files:
        for f in files:
            fname = f.get("name", "file")
            fcontent = f.get("content", "")
            ftype = f.get("type", "text")
            file_data_uri = fcontent if fcontent.startswith("data:") else f"data:application/octet-stream;base64,{fcontent}"
            content_parts.append({
                "type": "file",
                "file": {"filename": fname, "file_data": file_data_uri},
            })

    # 如果只有纯文本，content 直接用字符串
    if len(content_parts) == 1 and content_parts[0]["type"] == "text":
        msg_content = content_parts[0]["text"]
    elif content_parts:
        msg_content = content_parts
    else:
        msg_content = "(空消息)"

    # 构造 OpenAI 格式请求
    openai_payload = {
        "model": "mini-timebot",
        "messages": [{"role": "user", "content": msg_content}],
        "stream": True,
        "user": user_id,
        "password": password,
        "session_id": session_id,
        "enabled_tools": enabled_tools,
    }

    try:
        r = requests.post(
            LOCAL_OPENAI_COMPLETIONS_URL,
            json=openai_payload,
            headers={"Authorization": f"Bearer {user_id}:{password}"},
            stream=True,
            timeout=120,
        )
        if r.status_code == 401:
            session.clear()
            return jsonify({"error": "认证失败"}), 401
        if r.status_code != 200:
            return jsonify({"error": f"Agent 返回 {r.status_code}"}), r.status_code

        def generate():
            """将 OpenAI SSE 格式转为前端期望的简单 SSE 格式"""
            import json as _json
            for line in r.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if line.startswith("data: [DONE]"):
                    yield "data: [DONE]\n\n"
                    continue
                if line.startswith("data: "):
                    try:
                        chunk = _json.loads(line[6:])
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            # 转换为前端期望的简单 SSE 格式
                            text = content.replace("\\", "\\\\").replace("\n", "\\n")
                            yield f"data: {text}\n\n"
                    except _json.JSONDecodeError:
                        # 透传无法解析的行
                        yield line + "\n\n"

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/proxy_cancel", methods=["POST"])
def proxy_cancel():
    """代理取消请求到后端 Agent"""
    user_id = session.get("user_id")
    password = session.get("password")
    if not user_id or not password:
        return jsonify({"error": "未登录"}), 401
    session_id = request.json.get("session_id", "default") if request.is_json else "default"
    try:
        r = requests.post(LOCAL_AGENT_CANCEL_URL, json={"user_id": user_id, "password": password, "session_id": session_id}, timeout=5)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/proxy_tts", methods=["POST"])
def proxy_tts():
    """代理 TTS 请求到后端 Agent，返回 mp3 音频流"""
    user_id = session.get("user_id")
    password = session.get("password")
    if not user_id or not password:
        return jsonify({"error": "未登录"}), 401

    text = request.json.get("text", "")
    voice = request.json.get("voice")
    if not text.strip():
        return jsonify({"error": "文本不能为空"}), 400

    try:
        payload = {"user_id": user_id, "password": password, "text": text}
        if voice:
            payload["voice"] = voice
        r = requests.post(LOCAL_TTS_URL, json=payload, timeout=60)
        if r.status_code != 200:
            return jsonify({"error": f"TTS 服务错误: {r.status_code}"}), r.status_code

        return Response(
            r.content,
            mimetype="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=tts_output.mp3"},
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/proxy_tools")
def proxy_tools():
    """代理获取工具列表请求到后端 Agent"""
    try:
        r = requests.get(LOCAL_TOOLS_URL, headers={"X-Internal-Token": INTERNAL_TOKEN}, timeout=10)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e), "tools": []}), 500

@app.route("/proxy_logout", methods=["POST"])
def proxy_logout():
    session.clear()
    return jsonify({"status": "success"})


@app.route("/proxy_sessions")
def proxy_sessions():
    """代理获取用户会话列表"""
    user_id = session.get("user_id")
    password = session.get("password")
    if not user_id or not password:
        return jsonify({"error": "未登录"}), 401
    try:
        r = requests.post(LOCAL_SESSIONS_URL, json={"user_id": user_id, "password": password}, timeout=15)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/proxy_session_history", methods=["POST"])
def proxy_session_history():
    """代理获取指定会话的历史消息"""
    user_id = session.get("user_id")
    password = session.get("password")
    if not user_id or not password:
        return jsonify({"error": "未登录"}), 401
    sid = request.json.get("session_id", "")
    try:
        r = requests.post(LOCAL_SESSION_HISTORY_URL, json={
            "user_id": user_id, "password": password, "session_id": sid
        }, timeout=15)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/proxy_session_status", methods=["POST"])
def proxy_session_status():
    """代理检查会话是否有系统触发的新消息"""
    user_id = session.get("user_id")
    password = session.get("password")
    if not user_id or not password:
        return jsonify({"has_new_messages": False}), 200
    sid = request.json.get("session_id", "") if request.is_json else ""
    try:
        r = requests.post(LOCAL_SESSION_STATUS_URL, json={
            "user_id": user_id, "password": password, "session_id": sid
        }, timeout=5)
        return jsonify(r.json()), r.status_code
    except Exception:
        return jsonify({"has_new_messages": False}), 200


@app.route("/proxy_delete_session", methods=["POST"])
def proxy_delete_session():
    """代理删除会话请求到后端 Agent"""
    user_id = session.get("user_id")
    password = session.get("password")
    if not user_id or not password:
        return jsonify({"error": "未登录"}), 401
    sid = request.json.get("session_id", "") if request.is_json else ""
    try:
        r = requests.post(LOCAL_DELETE_SESSION_URL, json={
            "user_id": user_id, "password": password, "session_id": sid
        }, timeout=15)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===== Group Chat Proxy Routes =====

def _group_auth_headers():
    """构造群聊API的Authorization header"""
    user_id = session.get("user_id")
    password = session.get("password")
    if not user_id or not password:
        return None, None
    return user_id, {"Authorization": f"Bearer {user_id}:{password}"}


@app.route("/proxy_groups", methods=["GET"])
def proxy_list_groups():
    """代理列出用户群聊"""
    uid, headers = _group_auth_headers()
    if not uid:
        return jsonify([]), 200
    try:
        r = requests.get(f"http://127.0.0.1:{PORT_AGENT}/groups", headers=headers, timeout=10)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/proxy_groups", methods=["POST"])
def proxy_create_group():
    """代理创建群聊"""
    uid, headers = _group_auth_headers()
    if not uid:
        return jsonify({"error": "未登录"}), 401
    try:
        headers["Content-Type"] = "application/json"
        r = requests.post(f"http://127.0.0.1:{PORT_AGENT}/groups", json=request.get_json(silent=True), headers=headers, timeout=10)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/proxy_groups/<group_id>", methods=["GET"])
def proxy_get_group(group_id):
    """代理获取群聊详情"""
    uid, headers = _group_auth_headers()
    if not uid:
        return jsonify({"error": "未登录"}), 401
    try:
        r = requests.get(f"http://127.0.0.1:{PORT_AGENT}/groups/{group_id}", headers=headers, timeout=10)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/proxy_groups/<group_id>", methods=["PUT"])
def proxy_update_group(group_id):
    """代理更新群聊"""
    uid, headers = _group_auth_headers()
    if not uid:
        return jsonify({"error": "未登录"}), 401
    try:
        headers["Content-Type"] = "application/json"
        r = requests.put(f"http://127.0.0.1:{PORT_AGENT}/groups/{group_id}", json=request.get_json(silent=True), headers=headers, timeout=10)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/proxy_groups/<group_id>", methods=["DELETE"])
def proxy_delete_group(group_id):
    """代理删除群聊"""
    uid, headers = _group_auth_headers()
    if not uid:
        return jsonify({"error": "未登录"}), 401
    try:
        r = requests.delete(f"http://127.0.0.1:{PORT_AGENT}/groups/{group_id}", headers=headers, timeout=10)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/proxy_groups/<group_id>/messages", methods=["GET"])
def proxy_group_messages(group_id):
    """代理获取群聊消息（支持增量 after_id）"""
    uid, headers = _group_auth_headers()
    if not uid:
        return jsonify({"messages": []}), 200
    try:
        after_id = request.args.get("after_id", "0")
        r = requests.get(
            f"http://127.0.0.1:{PORT_AGENT}/groups/{group_id}/messages",
            params={"after_id": after_id},
            headers=headers, timeout=10,
        )
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/proxy_groups/<group_id>/messages", methods=["POST"])
def proxy_post_group_message(group_id):
    """代理发送群聊消息"""
    uid, headers = _group_auth_headers()
    if not uid:
        return jsonify({"error": "未登录"}), 401
    try:
        headers["Content-Type"] = "application/json"
        r = requests.post(
            f"http://127.0.0.1:{PORT_AGENT}/groups/{group_id}/messages",
            json=request.get_json(silent=True),
            headers=headers, timeout=10,
        )
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/proxy_groups/<group_id>/sessions", methods=["GET"])
def proxy_group_sessions(group_id):
    """代理获取可加入群聊的sessions"""
    uid, headers = _group_auth_headers()
    if not uid:
        return jsonify({"sessions": []}), 200
    try:
        r = requests.get(
            f"http://127.0.0.1:{PORT_AGENT}/groups/{group_id}/sessions",
            headers=headers, timeout=15,
        )
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"sessions": [], "error": str(e)}), 500


# ===== OASIS Proxy Routes =====

@app.route("/proxy_oasis/topics")
def proxy_oasis_topics():
    """Proxy: list OASIS discussion topics for the logged-in user."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify([]), 200
    try:
        print(f"[OASIS Proxy] Fetching topics from {OASIS_BASE_URL}/topics for user={user_id}")
        r = requests.get(f"{OASIS_BASE_URL}/topics", params={"user_id": user_id}, timeout=10)
        print(f"[OASIS Proxy] Response status: {r.status_code}, count: {len(r.json()) if r.text else 0}")
        return jsonify(r.json()), r.status_code
    except Exception as e:
        print(f"[OASIS Proxy] Error fetching topics: {e}")
        return jsonify([]), 200  # Return empty list on error


@app.route("/proxy_oasis/topics/<topic_id>")
def proxy_oasis_topic_detail(topic_id):
    """Proxy: get full detail of a specific OASIS discussion."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "未登录"}), 401
    try:
        url = f"{OASIS_BASE_URL}/topics/{topic_id}"
        print(f"[OASIS Proxy] Fetching topic detail from {url} for user={user_id}")
        r = requests.get(url, params={"user_id": user_id}, timeout=10)
        print(f"[OASIS Proxy] Detail response status: {r.status_code}")
        return jsonify(r.json()), r.status_code
    except Exception as e:
        print(f"[OASIS Proxy] Error fetching topic detail: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/proxy_oasis/topics/<topic_id>/stream")
def proxy_oasis_topic_stream(topic_id):
    """Proxy: SSE stream for real-time OASIS discussion updates."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "未登录"}), 401
    try:
        r = requests.get(
            f"{OASIS_BASE_URL}/topics/{topic_id}/stream",
            params={"user_id": user_id},
            stream=True, timeout=300,
        )
        if r.status_code != 200:
            return jsonify({"error": f"OASIS returned {r.status_code}"}), r.status_code

        def generate():
            for line in r.iter_lines(decode_unicode=True):
                if line:
                    yield line + "\n\n"

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/proxy_oasis/experts")
def proxy_oasis_experts():
    """Proxy: list all OASIS expert agents."""
    user_id = session.get("user_id", "")
    try:
        r = requests.get(f"{OASIS_BASE_URL}/experts", params={"user_id": user_id}, timeout=10)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/proxy_oasis/topics/<topic_id>/cancel", methods=["POST"])
def proxy_oasis_cancel_topic(topic_id):
    """Proxy: force-cancel a running OASIS discussion."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "未登录"}), 401
    try:
        r = requests.delete(f"{OASIS_BASE_URL}/topics/{topic_id}", params={"user_id": user_id}, timeout=10)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/proxy_oasis/topics/<topic_id>/purge", methods=["POST"])
def proxy_oasis_purge_topic(topic_id):
    """Proxy: permanently delete an OASIS discussion record."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "未登录"}), 401
    try:
        r = requests.post(f"{OASIS_BASE_URL}/topics/{topic_id}/purge", params={"user_id": user_id}, timeout=10)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/proxy_oasis/topics", methods=["DELETE"])
def proxy_oasis_purge_all_topics():
    """Proxy: delete all OASIS topics for the current user."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "未登录"}), 401
    try:
        r = requests.delete(f"{OASIS_BASE_URL}/topics", params={"user_id": user_id}, timeout=30)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT_FRONTEND", "51209")), debug=False, threaded=True)
