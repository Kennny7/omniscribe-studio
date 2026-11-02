# core-gateway

FastAPI REST API Gateway, WebSocket Multiplexer Hub, and Live Telemetry Streamer for OmniScribe Studio.

## Overview
- Unified REST endpoints for ingestion, chapter editing, and lore auditing.
- Bidirectional non-blocking WebSocket streams (`/ws/stream`) for chat and background progress.
- Dual-mode persistence controller supporting Docker enterprise services and local SQLite fallback.
