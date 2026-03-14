High-Level Specifications
​Layer 1: The Command Center (The Interface)
​Tech Stack: VS Code + GitHub Copilot (Agent Mode) + MCP Client.
​Role: The "Observation Deck." It allows the human founder to see what the autonomous boardroom is doing in real-time.
​Functionality: * Connects to the Layer 3 MCP Server via a remote URL.
​Exposes "Legendary" strategic insights directly in the IDE.
​Provides "One-Click Approval" for code or infrastructure changes proposed by the AI Boardroom.
​Layer 2: The Thinking Engine (The Brain)
​Tech Stack: Microsoft Agent Framework (Python) + Azure Functions.
​Role: The "Autonomous Boardroom." It operates 24/7 to solve problems and optimize the business.
​Functionality:
​Orchestration: Manages the dialectic debate between a CTO Agent and a CMO Agent.
​Tool Usage: It has no local memory; it must call Layer 3 tools to "remember" things or to "act" on Azure Bicep/Python files.
​Trigger: Runs on a timer (CRON) or via HTTP webhooks (e.g., triggered by a GitHub commit).
​Layer 3: The Persistent Subconscious (The Memory & Bridge)
​Tech Stack: Python + FastMCP + Azure Table Storage + Azure Functions.
​Role: The "Single Source of Truth." It bridges the gap between the cloud and the founder's desktop.
​Functionality:
​State Management: Stores every debate, resonance score, and decision in Azure Table Storage.
​Protocol: Implements the Model Context Protocol (MCP) to expose these memories as "Resources" and business actions as "Tools."
​Integration: Hosts the existing Python modules and Bicep templates as callable MCP tools.