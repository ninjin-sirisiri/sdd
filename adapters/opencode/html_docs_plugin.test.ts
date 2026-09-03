import { expect, test } from "bun:test"
import { mkdtemp, rm } from "node:fs/promises"
import { join } from "node:path"
import { tmpdir } from "node:os"

import {
  HtmlDocsPlugin,
  fileEditedPayloadToRequest,
  requirePolicyAllow,
  requestFromToolExecuteBefore,
} from "./html_docs_plugin.ts"

test("maps an OpenCode write payload to an allowable policy request", () => {
  expect(
    requestFromToolExecuteBefore(
      { tool: "write", sessionID: "session", callID: "call" },
      { args: { path: "CONTEXT.md", content: "changed" } },
    ),
  ).toEqual({
    operation: "edit",
    paths: ["CONTEXT.md"],
    new_source_paths: ["CONTEXT.md"],
  })
  expect(() => requirePolicyAllow({ decision: "allow", message: "allowed" })).not.toThrow()
})

test("maps policy denial to a before-hook error", () => {
  expect(() => requirePolicyAllow({ decision: "deny", message: "HTML-only edit denied" })).toThrow(
    "HTML-only edit denied",
  )
})

test("preserves explicit bootstrap options", () => {
  expect(
    requestFromToolExecuteBefore(
      { tool: "write" },
      { args: { path: "CONTEXT.html", bootstrap_paths: ["CONTEXT.html"] } },
    ),
  ).toEqual({
    operation: "edit",
    paths: ["CONTEXT.html"],
    bootstrap_paths: ["CONTEXT.html"],
  })
  expect(fileEditedPayloadToRequest({ type: "file.edited", properties: { file: "CONTEXT.md" } })).toEqual({
    operation: "edit",
    paths: ["CONTEXT.md"],
  })
})

test("bootstraps an existing companion before an OpenCode write without a custom argument", async () => {
  const directory = await mkdtemp(join(tmpdir(), "sdd-opencode-"))
  try {
    await Bun.write(join(directory, "CONTEXT.md"), "# Existing context\n")
    const hooks = await HtmlDocsPlugin({ directory, worktree: directory })

    await expect(
      hooks["tool.execute.before"](
        { tool: "write", sessionID: "session", callID: "call" },
        { args: { filePath: "CONTEXT.html", content: "<html>" } },
      ),
    ).resolves.toBeUndefined()
  } finally {
    await rm(directory, { recursive: true, force: true })
  }
})

test("rejects unknown and malformed payloads", () => {
  expect(() => requestFromToolExecuteBefore({ tool: "write" }, { args: {} })).toThrow("no file path")
  expect(() => fileEditedPayloadToRequest({ type: "file.watcher.updated", properties: {} })).toThrow(
    "unknown event",
  )
  expect(() => requirePolicyAllow({ decision: "error" })).toThrow("invalid decision")
})

test("runs exported hooks against OpenCode fixtures and reports post-edit feedback", async () => {
  const toolFixture = await Bun.file(new URL("./fixtures/tool_execute_before.json", import.meta.url)).json()
  const eventFixture = await Bun.file(new URL("./fixtures/file_edited.json", import.meta.url)).json()
  const toasts: unknown[] = []
  const hooks = await HtmlDocsPlugin({
    directory: process.cwd(),
    worktree: process.cwd(),
    client: {
      tui: {
        showToast: async (toast: unknown) => {
          toasts.push(toast)
        },
      },
    },
  })

  await hooks["tool.execute.before"](
    { tool: toolFixture.tool as string },
    toolFixture.output,
  )
  await hooks.event({ event: eventFixture })

  expect(toasts).toHaveLength(1)
  expect(toasts[0]).toMatchObject({
    body: { title: "HTML docs", variant: "info" },
  })
})
