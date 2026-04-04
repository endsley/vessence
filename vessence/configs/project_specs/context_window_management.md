# Project: Context Window Management

## 1. Description
This project is an ongoing effort to design and implement a sophisticated context and memory management system for both Jane and Amber. The goal is to ensure efficient use of LLM context windows, prevent overflow, and create a robust, self-improving long-term memory.

## 2. Core Components & Functionalities
-   **Tiered Memory Architecture:** A multi-layered memory system.
-   **Active Conversation Compaction:** A process to summarize the live conversation history to free up tokens.
-   **Intelligent End-of-Session Archival:** A process to distill valuable knowledge from a session's temporary memory into the permanent long-term memory.

---

## 3. Detailed Design: Intelligent Archival Process

### 3.1. Overview
This process runs at the end of each session to distill valuable information from the session's temporary short-term memory into the permanent long-term memory database.

### 3.2. Core Actor
- **Sub-agent:** Qwen 2.5 Coder 14b
- **Role:** "The Archivist"

### 3.3. Process Flow
1.  **Trigger:** Activates automatically at the end of a session.
2.  **Review:** The Archivist iterates through every memory in the session's short-term database.
3.  **Triage:** For each memory, it applies the criteria below to decide if it's "worth keeping."
4.  **Synthesize:** If a memory is kept, the Archivist searches the long-term DB for related facts. It then either creates a new, standalone memory or merges the new information with an existing memory, replacing the old one.
5.  **Cleanup:** Once all memories have been processed, the temporary short-term database for the session is deleted.

### 3.4. Triage Criteria

#### "Keep" Criteria (Promote to Long-Term Memory)
1.  **Explicit Directives & Preferences:** Any direct command on how I should operate.
2.  **New Factual Knowledge:** Verifiable facts about the user, our projects, or the environment.
3.  **Key Decisions & Resolutions:** The final, agreed-upon outcome after a discussion.
4.  **Architectural & Project Updates:** Any change to our system's architecture or a project's goals.
5.  **Code & Skill Creation:** A summary of any new script or function, including its purpose, file path, and usage instructions.
6.  **Project Goals & Milestones:** High-level project goals or the definition of a new phase.
7.  **Definitions & Clarifications:** When the user defines a specific term or clarifies an ambiguous concept.
8.  **Root Cause Analysis Conclusions:** The final conclusion of a debugging session linking an error to its cause.
9.  **Negative Constraints:** Explicit instructions about actions I should *never* take.
10. **Critical Resource Locators:** A newly provided URL, file path, or command essential for a project.
11. **Agent Summaries:** My own final summaries after completing a complex task.

#### "Discard" Criteria (Ignore and Do Not Promote)
1.  **Conversational Filler & Pleasantries:** Simple acknowledgments, greetings, transitions, and expressions of agreement.
2.  **Process-Oriented Statements:** My own statements about an immediate, transient action.
3.  **Simple Confirmation Questions:** My own questions asking for a simple yes/no confirmation.
4.  **Raw, Unprocessed Data:** The full content of a file, log, or tool output.
5.  **Failed/Corrected Actions:** The record of a failed tool call, especially if followed by a success.
6.  **Redundant/Superseded Information:** An earlier, less complete version of a fact that is fully captured later.
7.  **Intermediate/Draft Code:** Non-final code snippets from an iterative development process.
8.  **Apologies & Self-Corrections:** My own conversational apologies for making an error.
9.  **Vague Emotional Statements:** User expressions of emotion without an actionable directive.
10. **Exact Duplicates:** Any conversational turn that is a duplicate of a memory already slated for promotion.

---

## 4. Accomplishments
*   Project defined in `TODO_PROJECTS.md`.
*   Initial architecture for context layers (startup, long-term, short-term) established.
*   Qwen Librarian for long-term memory summarization implemented.
*   **Design for "Intelligent Archival" process completed** and documented herein.

## 5. Next Steps
-   **Implement the `ConversationManager`** and the end-of-session "Intelligent Archival" process.
-   Define and test the token threshold (starting at 75%) for triggering context compaction.
-   Evaluate the impact of the new memory architecture on overall performance and coherence.
