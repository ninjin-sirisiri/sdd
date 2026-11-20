import { expect, test } from "bun:test"

import {
  createHtmlDocsV2Plugin,
  v2FilesystemEventToV1,
  v2ToolInputToV1,
} from "./html_docs_v2_plugin.ts"

test("maps a V2 execute.before payload onto the V1 tool/args shape", () => {
  expect(
    v2ToolInputToV1({
      tool: "write",
      sessionID: "ses_1",
      agent: "build",
      messageID: "msg_1",
      id: "call_1",
      input: { path: "CONTEXT.md", content: "changed" },
    }),
  ).toEqual({
    input: { tool: "write", sessionID: "ses_1", callID: "call_1" },
    output: { args: { path: "CONTEXT.md", content: "changed" } },
  })
})

test("ignores payloads without a tool name or argument object", () => {
  expect(v2ToolInputToV1(undefined)).toBeUndefined()
  expect(v2ToolInputToV1({ tool: "", input: {} })).toBeUndefined()
  expect(v2ToolInputToV1({ tool: "write" })).toBeUndefined()
  expect(v2ToolInputToV1({ tool: "write", input: "nope" })).toBeUndefined()
})

test("rewrites filesystem.changed into the V1 file.edited event", () => {
  expect(
    v2FilesystemEventToV1({
      type: "filesystem.changed",
      data: { file: "/repo/CONTEXT.md", event: "change" },
    }),
  ).toEqual({ type: "file.edited", properties: { file: "/repo/CONTEXT.md" } })
})

test("ignores unrelated events and malformed filesystem events", () => {
  expect(v2FilesystemEventToV1({ type: "form.replied", data: { file: "x" } })).toBeUndefined()
  expect(v2FilesystemEventToV1({ type: "filesystem.changed" })).toBeUndefined()
  expect(v2FilesystemEventToV1({ type: "filesystem.changed", data: {} })).toBeUndefined()
  expect(v2FilesystemEventToV1({ type: "filesystem.changed", data: { file: "" } })).toBeUndefined()
  expect(v2FilesystemEventToV1(null)).toBeUndefined()
})

test("exports a V2 { id, setup } plugin object", () => {
  const plugin = createHtmlDocsV2Plugin()
  expect(typeof plugin.id).toBe("string")
  expect(plugin.id.length).toBeGreaterThan(0)
  expect(typeof plugin.setup).toBe("function")
})

test("registers the before hook and blocks a denied edit by throwing", async () => {
  const published: unknown[] = []
  const plugin = createHtmlDocsV2Plugin()
  await plugin.setup({
    location: { directory: process.cwd() },
    tool: {
      hook: async (name, callback) => {
        published.push({ name, callback })
      },
    },
  })
  expect(published).toHaveLength(1)
  const registration = published[0] as {
    name: string
    callback: (input: unknown) => Promise<void>
  }
  expect(registration.name).toBe("execute.before")

  // An edit outside the Target set is allowed by the policy, so the callback
  // resolves and the tool proceeds.
  await expect(
    registration.callback({
      tool: "write",
      id: "call_1",
      input: { path: "notes.txt", content: "hello" },
    }),
  ).resolves.toBeUndefined()

  // Rewriting a Target's companion without a Markdown edit is denied, so the
  // callback rejects and V2 blocks the tool call.
  await expect(
    registration.callback({
      tool: "write",
      id: "call_2",
      input: { path: "CONTEXT.html", content: "<html></html>" },
    }),
  ).rejects.toThrow()
})

test("does nothing when the host exposes no directory", async () => {
  const published: unknown[] = []
  const plugin = createHtmlDocsV2Plugin()
  await plugin.setup({
    tool: {
      hook: async (name, callback) => {
        published.push({ name, callback })
      },
    },
  })
  expect(published).toHaveLength(0)
})
