/**
 * OpenCode V2 wrapper for the pack's HTML documentation guard.
 *
 * The pack's `html_docs_plugin.ts` is written against the OpenCode V1 plugin
 * contract (a function that returns a hook object). OpenCode V2 does not load
 * that shape at all: a V2 module must default-export `{ id, setup }`. Registering
 * the V1 module globally therefore silently enforces nothing.
 *
 * This wrapper keeps the V1 module as the single source of policy translation
 * and re-exposes the same two behaviours through the V2 context:
 *
 *   - `tool.hook("execute.before", ...)` enforces the edit-check before a file
 *     tool runs, and throws to block a denied edit.
 *   - `event.subscribe(...)` delivers `filesystem.changed`; validation feedback
 *     is reported after a Target companion changes.
 *
 * It performs no policy reasoning itself. Every decision comes from
 * `scripts/html-docs` through the V1 module's exported helpers.
 */
import {
  invokePolicy,
  invokeValidation,
  requestFromFileEdited,
  requestFromToolExecuteBefore,
  requirePolicyAllow,
} from "./html_docs_plugin.ts"

type JsonRecord = Record<string, unknown>

export type V2Context = {
  location?: { directory?: string }
  event?: {
    subscribe(options?: { types?: string[] } | string): AsyncIterable<unknown>
  }
  tool?: {
    hook(
      name: string,
      callback: (input: JsonRecord) => void | Promise<void>,
    ): Promise<unknown>
  }
  client?: {
    tui?: { showToast?: (input: unknown) => Promise<unknown> }
    app?: { log?: (input: unknown) => Promise<unknown> }
  }
  [key: string]: unknown
}

export const PLUGIN_ID = "sdd-html-docs"

/** Tools whose arguments carry a Target path in the V1 adapter's shape. */
const FILE_TOOLS = new Set(["edit", "write", "multiedit", "notebookedit", "delete"])

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

/**
 * V2 `execute.before` receives `{ tool, id, sessionID, input }` where `input`
 * is the tool's own argument object. The V1 helper expects the tool name plus
 * `{ args }`, so adapt at the boundary rather than duplicating its parsing.
 */
export function v2ToolInputToV1(
  input: unknown,
): { input: { tool: string; sessionID?: string; callID?: string }; output: { args: JsonRecord } } | undefined {
  if (!isRecord(input)) return undefined
  const tool = input.tool
  if (typeof tool !== "string" || !tool) return undefined
  const args = input.input
  if (!isRecord(args)) return undefined
  return {
    input: {
      tool,
      ...(typeof input.sessionID === "string" ? { sessionID: input.sessionID } : {}),
      ...(typeof input.id === "string" ? { callID: input.id } : {}),
    },
    output: { args },
  }
}

/**
 * V2's `filesystem.changed` carries the path at `data.file` (with
 * `data.event` = add/change/unlink), not the V1 `properties.file` shape.
 * Rewrite it into the V1 event the common parser already understands.
 */
export function v2FilesystemEventToV1(event: unknown): JsonRecord | undefined {
  if (!isRecord(event)) return undefined
  if (event.type !== "filesystem.changed") return undefined
  const data = event.data
  if (!isRecord(data)) return undefined
  if (typeof data.file !== "string" || !data.file) return undefined
  return { type: "file.edited", properties: { file: data.file } }
}

async function feedback(
  client: unknown,
  message: string,
  variant: "info" | "error",
): Promise<void> {
  if (!isRecord(client)) return
  const tui = client.tui
  if (isRecord(tui) && typeof tui.showToast === "function") {
    await (tui.showToast as (value: unknown) => Promise<unknown>)({
      body: { title: "HTML docs", message, variant },
    })
    return
  }
  const app = client.app
  if (isRecord(app) && typeof app.log === "function") {
    await (app.log as (value: unknown) => Promise<unknown>)({
      body: { service: "html-docs", level: variant === "error" ? "error" : "info", message },
    })
  }
}

function resultMessage(result: { message?: unknown }): string {
  return typeof result.message === "string" && result.message
    ? result.message
    : "The html-docs policy completed."
}

export function createHtmlDocsV2Plugin() {
  return {
    id: PLUGIN_ID,
    async setup(context: V2Context): Promise<void> {
      const repositoryRoot = context.location?.directory
      if (typeof repositoryRoot !== "string" || repositoryRoot.length === 0) return

      // Enforce the edit order before file tools run. A denial throws, which is
      // how V2 blocks the tool call.
      try {
        await context.tool?.hook("execute.before", async (input) => {
          const mapped = v2ToolInputToV1(input)
          if (!mapped) return
          // The hook runs for every tool. Skip anything that is not a file
          // tool so unrelated calls (shell, grep, ...) never pay for a policy
          // process or risk its timeout.
          if (!FILE_TOOLS.has(mapped.input.tool)) return
          const policyRequest = requestFromToolExecuteBefore(
            mapped.input,
            mapped.output,
          )
          // Only file-tool calls carry paths. A request with no paths is not an
          // edit, so running the policy would spend a process and could time
          // out on unrelated tools such as `shell`.
          if (!policyRequest.paths.length) return
          // A denial must throw: that is how V2 blocks the tool call.
          requirePolicyAllow(await invokePolicy(repositoryRoot, policyRequest))
        })
      } catch (error) {
        await feedback(
          context.client,
          `HTML guard failed to register: ${error instanceof Error ? error.message : String(error)}. Run html-docs doctor.`,
          "error",
        )
      }

      // Validate and report after a companion changes. This is feedback only;
      // the Git / CI gate remains the enforcement boundary for writes that
      // bypass the tool hook.
      const stream = context.event?.subscribe({
        types: ["filesystem.changed"],
      })
      if (!stream) return
      ;(async () => {
        for await (const raw of stream) {
          const event = v2FilesystemEventToV1(raw)
          if (!event) continue
          try {
            const policyRequest = requestFromFileEdited(event)
            const htmlPaths = policyRequest.paths.filter((path) =>
              path.toLowerCase().endsWith(".html"),
            )
            const result = htmlPaths.length
              ? await invokeValidation(repositoryRoot, htmlPaths)
              : await invokePolicy(repositoryRoot, policyRequest)
            await feedback(
              context.client,
              resultMessage(result),
              result.decision === "deny" ? "error" : "info",
            )
          } catch (error) {
            await feedback(
              context.client,
              `HTML synchronization feedback failed: ${error instanceof Error ? error.message : String(error)}. Run html-docs doctor.`,
              "error",
            )
          }
        }
      })().catch(async (error: unknown) => {
        await feedback(
          context.client,
          `HTML event stream stopped: ${error instanceof Error ? error.message : String(error)}. Run html-docs doctor.`,
          "error",
        )
      })
    },
  }
}

const plugin = createHtmlDocsV2Plugin()
export default plugin
