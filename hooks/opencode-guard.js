import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";

// The rules stay in guard.py so OpenCode and Claude Code cannot drift apart.
const GUARD = process.env.UAS_GUARD || fileURLToPath(new URL("guard.py", import.meta.url));
// Windows ships the interpreter as "python"; "python3" there is usually absent or
// a Store stub, which would make the guard fail open on every call.
const PYTHON = process.env.UAS_PYTHON || (process.platform === "win32" ? "python" : "python3");

// Limited to the tool names OpenCode documents; a guessed name would read as
// coverage without providing any.
const TOOLS = { bash: "Bash", edit: "Edit", write: "Write" };

function payload(tool, args) {
  return JSON.stringify({
    tool_name: TOOLS[tool],
    tool_input: {
      command: args.command,
      content: args.content,
      new_string: args.newString ?? args.new_string,
    },
  });
}

export const UniversalAgentSkillsGuard = async () => ({
  "tool.execute.before": async (input, output) => {
    const tool = String(input?.tool ?? "").toLowerCase();
    if (!Object.hasOwn(TOOLS, tool) || !existsSync(GUARD)) return;

    const result = spawnSync(PYTHON, [GUARD], {
      input: payload(tool, output?.args ?? {}),
      encoding: "utf8",
      timeout: 10000,
    });

    // A missing interpreter or crashed guard must not block legitimate work.
    if (result.error || result.status !== 2) return;
    throw new Error(result.stderr.trim());
  },
});
