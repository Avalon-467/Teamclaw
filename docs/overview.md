# Overview

This page holds the higher-level product information that does not need to live in `README.md` or `SKILL.md`.

## What TeamClaw Is

TeamClaw is an OpenAI-compatible AI agent system with:

- a local `/v1/chat/completions` endpoint
- a built-in multi-expert orchestration engine called OASIS
- lightweight built-in agents for files, commands, and messaging
- optional integrations such as OpenClaw, Telegram, QQ, and Cloudflare Tunnel

## Core Concepts

### Team

A Team combines:

- agents
- experts / prompts
- workflows

This lets TeamClaw move beyond single-agent chat into structured collaboration.

### OASIS

OASIS is the workflow engine behind coordinated expert discussions and execution flows. It supports:

- sequential steps
- parallel branches
- conditional routing
- loops
- DAG-style dependency graphs

## Main Capabilities

- OpenAI-compatible chat API
- multi-session and multi-user isolation
- Web UI on the local machine
- scheduled tasks
- optional bot integration
- optional public exposure through Cloudflare Tunnel

## Typical Usage Modes

### Local assistant

Run TeamClaw on your own machine and use the local Web UI or the OpenAI-compatible API.

### Multi-expert orchestration

Create teams of experts and define workflows that debate, vote, summarize, or execute staged tasks.

### Integration hub

Use TeamClaw as a bridge layer for bots, external tools, or other OpenAI-compatible clients.

## Where To Go Next

- Installation, Windows / WSL setup, startup expectations, access notes, and audio setup: `SKILL.md`
- CLI usage: [cli.md](./cli.md)
- Ports and service map: [ports.md](./ports.md)
