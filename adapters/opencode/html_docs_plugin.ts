import { fileURLToPath } from "node:url"
import { isAbsolute, relative, resolve } from "node:path"

type JsonRecord = Record<string, unknown>

export type PolicyRequest = {
  operation: "edit"
  paths: string[]
  bootstrap_paths?: string[]
  new_source_paths?: string[]
}

export type PolicyResult = {
  decision: "allow" | "deny"
  message?: string
  [key: string]: unknown
}

export type ToolExecuteInput = {
  tool: string
  sessionID?: string
  callID?: string
}

export type ToolExecuteOutput = {
  args: JsonRecord
}

export type FileEditedEvent = {
  type: "file.edited"
  properties: { file: string; [key: string]: unknown }
}

export type PluginContext = {
  directory: string
  worktree?: string
  client?: unknown
  [key: string]: unknown
}

export type PluginHooks = {
  "tool.execute.before": (
    input: ToolExecuteInput,
    output: ToolExecuteOutput,
  ) => Promise<void>
  event: (input: { event: unknown }) => Promise<void>
}

const FILE_TOOLS = new Set(["edit", "write", "multiedit", "notebookedit", "delete"])
const PATH_KEYS = ["path", "filePath", "file_path", "notebookPath", "notebook_path"]
const LIST_KEYS = ["edits", "files", "changes"]
const POLICY_TIMEOUT_MS = 10_000
const POLICY_CLI = fileURLToPath(new URL("../../scripts/html-docs", import.meta.url))

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function inputError(message: string): Error {
  return new Error(`OpenCode hook payload is invalid: ${message}`)
}

function checkKeys(value: JsonRecord, allowed: Set<string>): void {
  const unknown = Object.keys(value).filter((key) => !allowed.has(key)).sort()
  if (unknown.length) throw inputError(`unknown field(s): ${unknown.join(", ")}`)
}

function collectPaths(value: unknown, result: string[]): void {
  if (!isRecord(value)) throw inputError("file-tool arguments must be an object")
  for (const key of PATH_KEYS) {
    if (!(key in value)) continue
    const path = value[key]
    if (typeof path !== "string" || path.length === 0) {
      throw inputError(`${key} must be a non-empty path`)
    }
    result.push(path)
  }
  for (const key of LIST_KEYS) {
    if (!(key in value)) continue
    const entries = value[key]
    if (!Array.isArray(entries)) throw inputError(`${key} must be an array`)
    for (const entry of entries) {
      if (typeof entry === "string") {
        if (!entry) throw inputError(`${key} contains an empty path`)
        result.push(entry)
      } else {
        collectPaths(entry, result)
      }
    }
  }
}

function optionsFrom(...values: JsonRecord[]): Pick<PolicyRequest, "bootstrap_paths" | "new_source_paths"> {
  const options: Pick<PolicyRequest, "bootstrap_paths" | "new_source_paths"> = {}
  for (const name of ["bootstrap_paths", "new_source_paths"] as const) {
    const source = values.find((value) => name in value)
    if (!source) continue
    const paths = source[name]
    if (!Array.isArray(paths) || paths.some((path) => typeof path !== "string" || !path)) {
      throw inputError(`${name} must be an array of non-empty paths`)
    }
    if (paths.length) options[name] = paths
  }
  return options
}

function request(paths: string[], ...values: JsonRecord[]): PolicyRequest {
  return {
    operation: "edit",
    paths: [...new Set(paths)],
    ...optionsFrom(...values),
  }
}

function repositoryRelative(root: string, path: string): string {
  const repositoryRoot = resolve(root)
  const candidate = resolve(isAbsolute(path) ? path : resolve(repositoryRoot, path))
  return relative(repositoryRoot, candidate).replaceAll("\\", "/")
}

function isTargetPath(relativePath: string, extension: ".md" | ".html"): boolean {
  const parts = relativePath.split("/")
  return (
    relativePath === `CONTEXT${extension}`
    || (parts.length === 3 && parts[0] === "docs" && parts[1] === "adr" && parts[2].endsWith(extension) && !parts[2].startsWith("."))
    || (parts.length === 4 && parts[0] === "docs" && parts[1] === "sdd" && (parts[2] === "specs" || parts[2] === "plans") && parts[3].endsWith(extension) && !parts[3].startsWith("."))
  )
}

function targetSourcePaths(paths: string[], root = process.cwd()): string[] {
  return [...new Set(paths.filter((path) => isTargetPath(repositoryRelative(root, path), ".md")))]
}

function targetBootstrapSourcePaths(root: string, paths: string[]): string[] {
  return [...new Set(paths.flatMap((path) => {
    const relativePath = repositoryRelative(root, path)
    if (!isTargetPath(relativePath, ".html")) return []
    return [relativePath.replace(/\.html$/, ".md")]
  }))]
}

function reportedBootstrapPaths(result: PolicyResult, sourcePaths: string[]): string[] {
  if (result.decision !== "allow" || !Array.isArray(result.paths)) return []
  const reported = new Set(result.paths.filter((path): path is string => typeof path === "string"))
  return sourcePaths
    .map((sourcePath) => sourcePath.replace(/\.md$/, ".html"))
    .filter((companionPath) => reported.has(companionPath))
}

export function requestFromToolExecuteBefore(
  input: unknown,
  output: unknown,
): PolicyRequest {
  if (!isRecord(input) || typeof input.tool !== "string" || !input.tool) {
    throw inputError("tool.execute.before input has no tool name")
  }
  checkKeys(input, new Set(["tool", "sessionID", "callID"]))
  if (!isRecord(output) || !isRecord(output.args)) {
    throw inputError("tool.execute.before output has no args object")
  }
  checkKeys(output, new Set(["args"]))
  const paths: string[] = []
  if (FILE_TOOLS.has(input.tool)) collectPaths(output.args, paths)
  if (FILE_TOOLS.has(input.tool) && paths.length === 0) {
    throw inputError(`${input.tool} has no file path`)
  }
  const policyRequest = request(paths, input, output.args)
  if (input.tool !== "write") return policyRequest
  const newSources = targetSourcePaths(paths)
  if (!newSources.length) return policyRequest
  return {
    ...policyRequest,
    new_source_paths: [...new Set([...(policyRequest.new_source_paths ?? []), ...newSources])],
  }
}

export function requestFromFileEdited(payload: unknown): PolicyRequest {
  const wrapped = isRecord(payload) && isRecord(payload.event)
  if (wrapped) checkKeys(payload, new Set(["event"]))
  const event = wrapped ? payload.event : payload
  if (!isRecord(event) || event.type !== "file.edited") {
    throw inputError("unknown event; only file.edited is supported")
  }
  checkKeys(event, new Set(["type", "id", "properties"]))
  const properties = event.properties
  if (!isRecord(properties) || typeof properties.file !== "string" || !properties.file) {
    throw inputError("file.edited has no file path")
  }
  checkKeys(properties, new Set(["file", "bootstrap_paths", "new_source_paths"]))
  return request([properties.file], properties)
}

export const toolPayloadToRequest = requestFromToolExecuteBefore
export const fileEditedPayloadToRequest = requestFromFileEdited

export function requirePolicyAllow(result: unknown): asserts result is PolicyResult {
  if (!isRecord(result) || (result.decision !== "allow" && result.decision !== "deny")) {
    throw new Error("html-docs policy returned an invalid decision")
  }
  if (result.decision === "deny") {
    const message = typeof result.message === "string" ? result.message : "HTML edit denied by policy"
    throw new Error(message)
  }
}

function resultMessage(result: PolicyResult): string {
  return typeof result.message === "string" && result.message
    ? result.message
    : "The html-docs policy completed."
}

export async function invokePolicy(
  directory: string,
  policyRequest: PolicyRequest,
): Promise<PolicyResult> {
  return invokeCli(directory, ["edit-check"], policyRequest)
}

export async function invokeValidation(
  directory: string,
  paths: string[],
): Promise<PolicyResult> {
  return invokeCli(directory, ["validate", ...paths])
}

export async function invokeBootstrap(
  directory: string,
  paths: string[],
): Promise<PolicyResult> {
  return invokeCli(directory, ["bootstrap", ...paths])
}

async function requestForToolExecuteBefore(
  directory: string,
  input: ToolExecuteInput,
  output: ToolExecuteOutput,
): Promise<PolicyRequest> {
  const policyRequest = requestFromToolExecuteBefore(input, output)
  if (input.tool !== "write" || policyRequest.bootstrap_paths?.length) return policyRequest

  // OpenCode's built-in write schema cannot carry bootstrap_paths, so obtain the
  // bounded grant for an eligible companion in the same before-hook operation.
  const sourcePaths = targetBootstrapSourcePaths(directory, policyRequest.paths)
  if (!sourcePaths.length) return policyRequest

  const bootstrapResult = await invokeBootstrap(directory, sourcePaths)
  const bootstrapPaths = reportedBootstrapPaths(bootstrapResult, sourcePaths)
  if (!bootstrapPaths.length) return policyRequest
  return { ...policyRequest, bootstrap_paths: bootstrapPaths }
}

async function invokeCli(
  directory: string,
  arguments_: string[],
  input?: PolicyRequest,
): Promise<PolicyResult> {
  const python = process.env.SDD_PYTHON || "python3"
  const child = Bun.spawn([python, POLICY_CLI, ...arguments_], {
    cwd: directory,
    stdin: "pipe",
    stdout: "pipe",
    stderr: "pipe",
  })
  let timedOut = false
  const timer = setTimeout(() => {
    timedOut = true
    child.kill()
  }, POLICY_TIMEOUT_MS)
  try {
    if (input !== undefined) child.stdin.write(JSON.stringify(input))
    child.stdin.end()
    const exitCode = await child.exited
    if (timedOut) throw new Error("html-docs policy timed out; run html-docs doctor")
    if (exitCode !== 0 && exitCode !== 1) {
      throw new Error(`html-docs policy failed with exit code ${exitCode}; run html-docs doctor`)
    }
    const output = await new Response(child.stdout).text()
    let parsed: unknown
    try {
      parsed = JSON.parse(output)
    } catch (error) {
      throw new Error(`html-docs policy returned invalid JSON: ${String(error)}`)
    }
    if (!isRecord(parsed) || (parsed.decision !== "allow" && parsed.decision !== "deny")) {
      throw new Error("html-docs policy returned an invalid decision")
    }
    if ((exitCode === 0 && parsed.decision !== "allow") || (exitCode === 1 && parsed.decision !== "deny")) {
      throw new Error("html-docs policy returned an inconsistent exit status")
    }
    return parsed as PolicyResult
  } catch (error) {
    if (child.exitCode === null) child.kill()
    throw error
  } finally {
    clearTimeout(timer)
  }
}

async function feedback(client: unknown, message: string, variant: "info" | "error"): Promise<void> {
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

export const HtmlDocsPlugin = async (context: PluginContext): Promise<PluginHooks> => {
  const repositoryRoot = context.worktree || context.directory
  return {
    "tool.execute.before": async (input, output) => {
      const policyRequest = await requestForToolExecuteBefore(repositoryRoot, input, output)
      const result = await invokePolicy(repositoryRoot, policyRequest)
      requirePolicyAllow(result)
    },
    event: async ({ event }) => {
      if (!isRecord(event) || event.type !== "file.edited") return
      try {
        const policyRequest = requestFromFileEdited(event)
        const htmlPaths = policyRequest.paths.filter((path) => path.toLowerCase().endsWith(".html"))
        const result = htmlPaths.length
          ? await invokeValidation(repositoryRoot, htmlPaths)
          : await invokePolicy(repositoryRoot, policyRequest)
        await feedback(context.client, resultMessage(result), result.decision === "deny" ? "error" : "info")
      } catch (error) {
        await feedback(
          context.client,
          `HTML synchronization feedback failed: ${error instanceof Error ? error.message : String(error)}. Run html-docs doctor.`,
          "error",
        )
      }
    },
  }
}

export default HtmlDocsPlugin
