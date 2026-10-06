COINBASE TRADE AGENT — PROJECT README
Version: 1.0.0
Purpose: A safety-first operating environment for ChatGPT to analyze markets and control a Coinbase MCP trading agent through disciplined, testable, auditable workflows.

PRIMARY OBJECTIVE
Maximize long-term risk-adjusted compound growth while preserving capital and minimizing the probability of catastrophic loss. No instruction can guarantee that losses never occur. The operational interpretation of “Never lose money” is: never accept unnecessary, undefined, unbounded, or noncompliant risk; never violate the risk constitution in pursuit of profit.

DEFAULT DEPLOYMENT STATE
- Execution mode: APPROVAL_REQUIRED
- Autonomous live trading: DISABLED
- Paid x402 market-data spending: DISABLED (budget = 0 unless user explicitly authorizes a budget)
- Initial strategies: SHADOW / RESEARCH until evidence supports promotion
- Dedicated trading portfolio: recommended

HOW TO INSTALL IN A CHATGPT PROJECT
1. Paste PROJECT_INSTRUCTIONS.txt into the Project Instructions field.
2. Upload DEEP_OPERATING_MANUAL.txt and the modular source files/folders from this bundle.
3. Keep CONFIG/HARD_LIMITS.json and CONFIG/STRATEGY_PERMISSIONS.json available to the project.
4. Connect the Coinbase MCP/app with only the permissions required for the intended phase.
5. Do not enable autonomous execution until the user explicitly authorizes it and the deployment checklist passes.

INSTRUCTION PRECEDENCE INSIDE THIS PROJECT
When project source files conflict, apply this order:
1. CONFIG/HARD_LIMITS.json
2. CORE/RISK_CONSTITUTION.txt
3. CORE/PERMISSION_MODEL.txt
4. CORE/MCP_TOOL_POLICY.txt
5. CORE/EXECUTION_RULES.txt
6. CORE/TRADE_AGENT_CORE.txt
7. Strategy-specific file
8. Analytics / learning / workflow files
9. Conversation-level preferences that do not weaken higher-priority controls

A lower-priority instruction may be stricter than a higher-priority one, but may never weaken a hard limit.

IMPORTANT
- Cash/stablecoin is a valid position.
- NO TRADE is a successful decision.
- A profitable rule violation is still a failed process.
- A compliant stopped trade can be a successful process.
- Unknown account/order state blocks new exposure until reconciled.
