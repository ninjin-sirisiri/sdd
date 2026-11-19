import { afterEach, beforeEach, describe, expect, test } from "bun:test"
import { mkdtemp, rm } from "node:fs/promises"
import { join } from "node:path"
import { tmpdir } from "node:os"

import {
  DESIGN_TOOL_NAME,
  PLUGIN_ID,
  answerMapForRegistration,
  buildHostQuestions,
  correlationFromMessageID,
  createDesignHistoryPlugin,
  createDesignQuestionTool,
  createRegistrationTable,
  eventBelongsToCheckout,
  fieldKeyFor,
  handleFormEvent,
  messageIDFor,
  questionIDFor,
  registrationFromCreatedEvent,
  summarizeHostResult,
  type DesignRegistration,
  type FormEvent,
  type HostTool,
  type HostToolContext,
  type Recorder,
  type RecorderPayload,
} from "./design_history_plugin.ts"

const CHECKOUT = "/tmp/sdd-checkout"

function recorderSpy() {
  const payloads: RecorderPayload[] = []
  const recorder: Recorder = async (payload) => {
    payloads.push(payload)
    return { ok: true }
  }
  return { payloads, recorder }
}

function seedRegistration(table = createRegistrationTable()): {
  table: ReturnType<typeof createRegistrationTable>
  registration: DesignRegistration
} {
  const token = "0123456789abcdef"
  table.addPending({
    correlation: token,
    case: "checkout-cancel",
    checkout: CHECKOUT,
    sessionID: "ses_one",
    title: "Design interview: checkout-cancel",
    questions: [
      {
        text: "削除は取り消せますか",
        header: "削除",
        options: [{ label: "取り消せる" }, { label: "取り消せない" }],
      },
      { text: "対象外はありますか", header: "対象外" },
    ],
    createdAt: Date.now(),
  })
  const event: FormEvent = {
    type: "form.created",
    id: "evt_1",
    data: {
      form: {
        id: "frm_one",
        sessionID: "ses_one",
        title: "Questions",
        metadata: { kind: "question", tool: { messageID: messageIDFor(token) } },
        fields: [
          {
            key: "q0",
            title: "削除",
            description: "削除は取り消せますか",
            type: "string",
            options: [{ value: "取り消せる", label: "取り消せる" }, { value: "取り消せない", label: "取り消せない" }],
            custom: true,
          },
          { key: "q1", title: "対象外", description: "対象外はありますか", type: "string", options: [], custom: true },
        ],
      },
    },
  }
  const registration = registrationFromCreatedEvent(event, table, CHECKOUT)
  if (!registration) throw new Error("fixture registration failed")
  return { table, registration }
}

describe("plugin identity", () => {
  test("default export is a V2 { id, setup } object", async () => {
    const module = await import("./design_history_plugin.ts")
    expect(module.default.id).toBe(PLUGIN_ID)
    expect(typeof module.default.setup).toBe("function")
  })
})

describe("registration table", () => {
  test("a pending presentation is consumed by the matching message ID", () => {
    const { table, registration } = seedRegistration()
    expect(registration.case).toBe("checkout-cancel")
    expect(registration.questions.map((question) => question.fieldKey)).toEqual(["q0", "q1"])
    expect(registration.questions[0].questionID).toBe("checkout-cancel.q1-削除は取り消せますか")
    expect(table.confirmedCount()).toBe(1)
    expect(table.pendingCount()).toBe(0)
    expect(correlationFromMessageID(messageIDFor("0123456789abcdef"))).toBe("0123456789abcdef")
    expect(correlationFromMessageID("msg_other")).toBeUndefined()
  })

  test("an unrelated form with no correlation is not a design form", () => {
    const table = createRegistrationTable()
    const unrelated: FormEvent = {
      type: "form.created",
      data: {
        form: {
          id: "frm_other",
          sessionID: "ses_one",
          title: "Questions",
          metadata: { kind: "question", tool: { messageID: "msg_plain" } },
          fields: [{ key: "q0", title: "Q", type: "string" }],
        },
      },
    }
    expect(registrationFromCreatedEvent(unrelated, table, CHECKOUT)).toBeUndefined()
    expect(table.confirmedCount()).toBe(0)
  })

  test("a correlation from another session is rejected", () => {
    const table = createRegistrationTable()
    const token = "abcdef0123456789"
    table.addPending({
      correlation: token,
      case: "case",
      checkout: CHECKOUT,
      sessionID: "ses_original",
      title: "Design",
      questions: [{ text: "Q" }],
      createdAt: Date.now(),
    })
    const event: FormEvent = {
      type: "form.created",
      data: {
        form: {
          id: "frm_x",
          sessionID: "ses_other",
          title: "Questions",
          metadata: { tool: { messageID: messageIDFor(token) } },
          fields: [{ key: "q0", title: "Q", type: "string" }],
        },
      },
    }
    expect(registrationFromCreatedEvent(event, table, CHECKOUT)).toBeUndefined()
    // The pending entry is consumed, so a late replay cannot hijack it either.
    expect(table.pendingCount()).toBe(0)
  })
})

describe("answer correlation", () => {
  test("maps host field keys to stable question IDs", () => {
    const { registration } = seedRegistration()
    const mapped = answerMapForRegistration(registration, {
      q0: "取り消せる",
      q1: "監査ログのみ",
    })
    expect(mapped.answers).toEqual({
      "checkout-cancel.q1-削除は取り消せますか": "取り消せる",
      "checkout-cancel.q2-対象外はありますか": "監査ログのみ",
    })
    expect(mapped.unknown).toEqual([])
  })

  test("reports unknown keys instead of inventing answers", () => {
    const { registration } = seedRegistration()
    const mapped = answerMapForRegistration(registration, { q9: "value" })
    expect(mapped.answers).toEqual({})
    expect(mapped.unknown).toEqual(["q9"])
  })

  test("two questions sharing an option label stay distinct", () => {
    const table = createRegistrationTable()
    table.register({
      case: "case-shared",
      checkout: CHECKOUT,
      sessionID: "ses_s",
      formID: "frm_s",
      title: "Design",
      correlation: "corr",
      questions: [
        {
          questionID: "case-shared.q_deploy",
          fieldKey: "q0",
          ordinal: 0,
          text: "配信方法",
          options: [{ label: "一括" }, { label: "段階的" }],
        },
        {
          questionID: "case-shared.q_rollback",
          fieldKey: "q1",
          ordinal: 1,
          text: "切り戻し方法",
          options: [{ label: "一括" }, { label: "段階的" }],
        },
      ],
    })
    const mapped = answerMapForRegistration(table.lookup("ses_s", "frm_s")!, {
      q0: "一括",
      q1: "段階的",
    })
    expect(mapped.answers).toEqual({
      "case-shared.q_deploy": "一括",
      "case-shared.q_rollback": "段階的",
    })
  })
})

describe("event handling", () => {
  test("created registers the form and reply records the raw answer map", async () => {
    const table = createRegistrationTable()
    const token = "0123456789abcdef"
    table.addPending({
      correlation: token,
      case: "checkout-cancel",
      checkout: CHECKOUT,
      sessionID: "ses_one",
      title: "Design interview: checkout-cancel",
      questions: [
        {
          text: "削除は取り消せますか",
          header: "削除",
          options: [{ label: "取り消せる" }, { label: "取り消せない" }],
        },
        { text: "対象外はありますか", header: "対象外" },
      ],
      createdAt: Date.now(),
    })
    const { payloads, recorder } = recorderSpy()
    const options = { checkout: CHECKOUT, recorder, registrations: table }
    const created = await handleFormEvent(
      {
        type: "form.created",
        id: "evt_1",
        data: {
          form: {
            id: "frm_one",
            sessionID: "ses_one",
            title: "Questions",
            metadata: { tool: { messageID: messageIDFor(token) } },
            fields: [
              { key: "q0", title: "削除", type: "string", options: [{ value: "取り消せる", label: "取り消せる" }] },
              { key: "q1", title: "対象外", type: "string", options: [] },
            ],
          },
        },
      },
      options,
    )
    expect(created).toEqual({ ok: true })
    expect(payloads[0]).toMatchObject({
      action: "register",
      case: "checkout-cancel",
      sessionID: "ses_one",
      formID: "frm_one",
      checkout: CHECKOUT,
    })

    await handleFormEvent(
      {
        type: "form.replied",
        location: { directory: CHECKOUT },
        data: {
          id: "frm_one",
          sessionID: "ses_one",
          answer: { q0: "取り消せる", q1: "監査ログのみ" },
        },
      },
      options,
    )
    expect(payloads[1]).toMatchObject({
      action: "reply",
      formID: "frm_one",
      recordMissing: true,
      delivery: "event",
    })
    expect(payloads[1].answers).toEqual({
      "checkout-cancel.q1-削除は取り消せますか": "取り消せる",
      "checkout-cancel.q2-対象外はありますか": "監査ログのみ",
    })
  })

  test("cancel is recorded without deleting earlier answers", async () => {
    const { table } = seedRegistration()
    const { payloads, recorder } = recorderSpy()
    const options = { checkout: CHECKOUT, recorder, registrations: table }
    await handleFormEvent(
      {
        type: "form.cancelled",
        location: { directory: CHECKOUT },
        data: { id: "frm_one", sessionID: "ses_one" },
      },
      options,
    )
    expect(payloads[0]).toMatchObject({ action: "cancel", formID: "frm_one" })
  })

  test("an unanswered or unregistered form is not recorded", async () => {
    const { table } = seedRegistration()
    const { payloads, recorder } = recorderSpy()
    const options = { checkout: CHECKOUT, recorder, registrations: table }
    expect(
      await handleFormEvent(
        {
          type: "form.replied",
          location: { directory: CHECKOUT },
          data: { id: "frm_unregistered", sessionID: "ses_one", answer: { q0: "x" } },
        },
        options,
      ),
    ).toBeUndefined()
    expect(payloads).toEqual([])
  })

  test("an answer from another checkout is not recorded", async () => {
    const { table } = seedRegistration()
    const { payloads, recorder } = recorderSpy()
    const logs: string[] = []
    const options = {
      checkout: CHECKOUT,
      recorder,
      registrations: table,
      log: (message: string) => logs.push(message),
    }
    expect(
      await handleFormEvent(
        {
          type: "form.replied",
          location: { directory: "/tmp/other-checkout" },
          data: { id: "frm_one", sessionID: "ses_one", answer: { q0: "取り消せる" } },
        },
        options,
      ),
    ).toBeUndefined()
    expect(payloads).toEqual([])
    expect(logs[0]).toContain("another checkout")
  })

  test("re-delivering the same event does not write twice", async () => {
    const { table } = seedRegistration()
    const { payloads, recorder } = recorderSpy()
    const seenEvents = new Set<string>()
    const options = { checkout: CHECKOUT, recorder, registrations: table, seenEvents }
    const event: FormEvent = {
      type: "form.replied",
      id: "evt_dup",
      location: { directory: CHECKOUT },
      data: { id: "frm_one", sessionID: "ses_one", answer: { q0: "取り消せる" } },
    }
    await handleFormEvent(event, options)
    await handleFormEvent(event, options)
    expect(payloads).toHaveLength(1)
  })

  test("checkout matching ignores a trailing slash only", () => {
    const { registration } = seedRegistration()
    expect(eventBelongsToCheckout({ type: "form.replied", location: { directory: `${CHECKOUT}/` } }, registration)).toBe(true)
    expect(eventBelongsToCheckout({ type: "form.replied", location: { directory: "/tmp/other" } }, registration)).toBe(false)
    expect(eventBelongsToCheckout({ type: "form.replied" }, registration)).toBe(true)
  })
})

describe("host payload construction", () => {
  test("preserves option presentation order and rejects empty questions", () => {
    expect(
      buildHostQuestions([
        {
          text: "配信方法は?",
          header: "配信",
          options: [{ label: "カナリア", description: "5% から" }, { label: "一括" }],
        },
      ]),
    ).toEqual([
      {
        question: "配信方法は?",
        header: "配信",
        options: [{ label: "カナリア", description: "5% から" }, { label: "一括" }],
      },
    ])
    expect(() => buildHostQuestions([])).toThrow("at least one question")
  })

  test("question IDs are stable and readable", () => {
    expect(questionIDFor("case-a", { text: "配信方法は?" }, 0)).toBe("case-a.q1-配信方法は")
    expect(questionIDFor("case-a", { text: "Rollout strategy?" }, 1)).toBe("case-a.q2-rollout-strategy")
    expect(questionIDFor("case-a", { text: "x", questionID: "explicit" }, 0)).toBe("explicit")
    expect(fieldKeyFor(3)).toBe("q3")
  })
})

describe("design question tool", () => {
  test("declares an output schema so the host can encode its result", () => {
    // Verified on 2.2.7 with a real model call: a bare-string return crashes
    // the dispatcher (`"output" in a`), and `{ output }` without a declared
    // schema fails with "Tool result declared output without an output schema".
    const tool = createDesignQuestionTool({
      checkout: CHECKOUT,
      recorder: recorderSpy().recorder,
      registrations: createRegistrationTable(),
      findQuestionTool: async () => undefined,
    })
    expect(tool.output).toEqual({ type: "string" })
  })

  test("presents through the host question tool and never returns the answers", async () => {
    const table = createRegistrationTable()
    const { payloads, recorder } = recorderSpy()
    const seen: Array<{ input: unknown; context: HostToolContext }> = []
    const hostTool: HostTool = {
      name: "question",
      async execute(input, context) {
        seen.push({ input, context })
        const messageID = context.messageID as string
        const handlerOptions = { checkout: CHECKOUT, recorder, registrations: table }
        // Emulate the host: publish form.created before the answer returns.
        await handleFormEvent(
          {
            type: "form.created",
            id: "evt_created",
            location: { directory: CHECKOUT },
            data: {
              form: {
                id: "frm_tool",
                sessionID: context.sessionID,
                title: "Questions",
                metadata: { kind: "question", tool: { messageID } },
                fields: [
                  { key: "q0", title: "削除", type: "string", options: [{ value: "取り消せる", label: "取り消せる" }] },
                  { key: "q1", title: "対象外", type: "string", options: [] },
                ],
              },
            },
          },
          handlerOptions,
        )
        await handleFormEvent(
          {
            type: "form.replied",
            id: "evt_replied",
            location: { directory: CHECKOUT },
            data: {
              id: "frm_tool",
              sessionID: context.sessionID,
              answer: { q0: "取り消せる", q1: "監査ログのみ" },
            },
          },
          handlerOptions,
        )
        return {
          output: { answers: [["取り消せる"], ["監査ログのみ"]] },
          content: 'User has answered your questions: "削除は取り消せますか"="取り消せる"',
          metadata: { answers: [["取り消せる"], ["監査ログのみ"]] },
        }
      },
    }
    const tool = createDesignQuestionTool({
      checkout: CHECKOUT,
      recorder,
      registrations: table,
      findQuestionTool: async () => hostTool,
      correlation: () => "feedfacefeedface",
      writeTimeoutMs: 2_000,
    })
    const context: HostToolContext = { sessionID: "ses_tool", messageID: "msg_original" }
    const output = await tool.execute(
      {
        case: "case-tool",
        title: "設計の確認",
        questions: [
          { text: "削除は取り消せますか", header: "削除", options: [{ label: "取り消せる" }, { label: "取り消せない" }] },
          { text: "対象外は?", header: "対象外" },
        ],
      },
      context,
    )
    expect(seen).toHaveLength(1)
    expect(seen[0].context.messageID).toBe(messageIDFor("feedfacefeedface"))
    expect(seen[0].input).toMatchObject({
      questions: [
        { question: "削除は取り消せますか", header: "削除", options: [{ label: "取り消せる" }, { label: "取り消せない" }] },
        { question: "対象外は?", header: "対象外", options: [] },
      ],
    })
    expect(output.output).toContain("recorded in the design history")
    expect(output.output).not.toContain("取り消せる")
    expect(output.output).not.toContain("監査ログのみ")
    expect(output).toHaveProperty("output")
    expect(table.pendingCount()).toBe(0)
    expect(table.confirmedCount()).toBe(1)
    expect(payloads.map((payload) => payload.action)).toEqual(["register", "reply"])
  })

  test("reports a failed answer write instead of claiming success", async () => {
    const table = createRegistrationTable()
    let replyCalls = 0
    const recorder: Recorder = async (payload) => {
      if (payload.action === "reply") {
        replyCalls += 1
        return { ok: false, detail: "disk full" }
      }
      return { ok: true }
    }
    const hostTool: HostTool = {
      name: "question",
      async execute(_input, context) {
        const handlerOptions = { checkout: CHECKOUT, recorder, registrations: table }
        await handleFormEvent(
          {
            type: "form.created",
            id: "evt_created",
            data: {
              form: {
                id: "frm_write_fail",
                sessionID: context.sessionID,
                title: "Questions",
                metadata: { tool: { messageID: context.messageID as string } },
                fields: [{ key: "q0", title: "Q", type: "string" }],
              },
            },
          },
          handlerOptions,
        )
        await handleFormEvent(
          {
            type: "form.replied",
            id: "evt_replied",
            location: { directory: CHECKOUT },
            data: { id: "frm_write_fail", sessionID: context.sessionID, answer: { q0: "A" } },
          },
          handlerOptions,
        )
        return { output: { answers: [["A"]] } }
      },
    }
    const tool = createDesignQuestionTool({
      checkout: CHECKOUT,
      recorder,
      registrations: table,
      findQuestionTool: async () => hostTool,
      correlation: () => "0011223344556677",
      writeTimeoutMs: 500,
    })
    const output = await tool.execute(
      { case: "case-fail", questions: [{ text: "Q", options: [{ label: "A" }] }] },
      { sessionID: "ses_fail", messageID: "msg" },
    )
    expect(replyCalls).toBe(1)
    expect(output.output).toContain("answer write failed")
    expect(output.output).toContain("disk full")
    expect(output.output).not.toContain("recorded in the design history")
  })

  test("reports event loss instead of inventing a recording", async () => {
    const table = createRegistrationTable()
    const { payloads, recorder } = recorderSpy()
    const tool = createDesignQuestionTool({
      checkout: CHECKOUT,
      recorder,
      registrations: table,
      findQuestionTool: async () => ({
        name: "question",
        async execute() {
          // The host answers, but no form.created / form.replied arrives.
          return { output: { answers: [["取り消せる"]] } }
        },
      }),
      correlation: () => "deadbeefdeadbeef",
      writeTimeoutMs: 120,
    })
    const output = await tool.execute(
      { case: "case-loss", questions: [{ text: "Q", options: [{ label: "A" }] }] },
      { sessionID: "ses_loss", messageID: "msg" },
    )
    expect(output.output).toContain("was not recorded")
    expect(payloads).toEqual([])
    expect(table.pendingCount()).toBe(0)
  })

  test("a missing host question tool records nothing", async () => {
    const table = createRegistrationTable()
    const { payloads, recorder } = recorderSpy()
    const tool = createDesignQuestionTool({
      checkout: CHECKOUT,
      recorder,
      registrations: table,
      findQuestionTool: async () => undefined,
      correlation: () => "abcabcabcabcabc1",
    })
    const output = await tool.execute(
      { case: "case-none", questions: [{ text: "Q", options: [{ label: "A" }] }] },
      { sessionID: "ses_none", messageID: "msg" },
    )
    expect(output.output).toContain("no design answer was recorded")
    expect(payloads).toEqual([])
    expect(table.pendingCount()).toBe(0)
  })

  test("a cancelled form is reported and leaves no pending registration", async () => {
    const table = createRegistrationTable()
    const { payloads, recorder } = recorderSpy()
    const tool = createDesignQuestionTool({
      checkout: CHECKOUT,
      recorder,
      registrations: table,
      findQuestionTool: async () => ({
        name: "question",
        async execute() {
          throw new Error("The user dismissed this question")
        },
      }),
      correlation: () => "cafebabecafebabe",
    })
    const output = await tool.execute(
      { case: "case-cancel", questions: [{ text: "Q", options: [{ label: "A" }] }] },
      { sessionID: "ses_cancel", messageID: "msg" },
    )
    expect(output.output).toContain("cancelled")
    expect(payloads).toEqual([])
    expect(table.pendingCount()).toBe(0)
  })

  test("a permission denial is reported as a host refusal, not a cancellation", async () => {
    const table = createRegistrationTable()
    const { payloads, recorder } = recorderSpy()
    const tool = createDesignQuestionTool({
      checkout: CHECKOUT,
      recorder,
      registrations: table,
      findQuestionTool: async () => ({
        name: "question",
        async execute() {
          // Verified live on 2.2.7: an agent without the `question` permission
          // throws this before any form is created.
          throw new Error("Permission denied: question")
        },
      }),
      correlation: () => "0badc0de0badc0de",
    })
    const output = await tool.execute(
      { case: "case-denied", questions: [{ text: "Q", options: [{ label: "A" }] }] },
      { sessionID: "ses_denied", messageID: "msg" },
    )
    expect(output.output).toContain("denied the question permission")
    expect(output.output).toContain("no answer was recorded")
    expect(output.output).not.toContain("cancelled")
    expect(payloads).toEqual([])
    expect(table.pendingCount()).toBe(0)
  })

  test("summarizer counts answered questions without echoing values", () => {
    expect(summarizeHostResult({ output: { answers: [["a"], []] } })).toContain("1/2")
    expect(summarizeHostResult({ output: { answers: [["a"], []] } })).not.toContain('"a"')
    expect(summarizeHostResult(undefined)).toContain("not repeated")
  })
})

describe("plugin setup", () => {
  test("registers the design tool and filters subscription events by type", async () => {
    const added: HostTool[] = []
    const hooked: string[] = []
    const events: FormEvent[] = []
    let deliver: ((event: FormEvent) => void) | undefined
    const table = createRegistrationTable()
    const payloads: RecorderPayload[] = []
    const plugin = createDesignHistoryPlugin({
      checkout: CHECKOUT,
      registrations: table,
      recorder: async (payload) => {
        payloads.push(payload)
        return { ok: true }
      },
      log: () => {},
    })
    await plugin.setup({
      location: { directory: CHECKOUT },
      permission: {
        async hook(name) {
          hooked.push(name)
          return undefined
        },
      },
      tool: {
        async transform(callback) {
          callback({
            get(name: string) {
              return added.find((tool) => tool.name === name)
            },
            add(tool: HostTool) {
              added.push(tool)
              return tool
            },
          })
          return undefined
        },
        async list() {
          return []
        },
      },
      event: {
        subscribe() {
          return {
            async *[Symbol.asyncIterator]() {
              while (true) {
                const next = await new Promise<FormEvent | undefined>((resolve) => {
                  deliver = (event) => resolve(event)
                })
                if (!next) return
                events.push(next)
                yield next
              }
            },
          }
        },
      },
    })
    expect(added.map((tool) => tool.name)).toEqual([DESIGN_TOOL_NAME])
    expect(hooked).toEqual(["evaluate"])

    // Deliver a non-form event: it must be ignored.
    deliver?.({ type: "session.created" } as FormEvent)
    // Deliver a form.created that the plugin did not present.
    deliver?.({
      type: "form.created",
      data: {
        form: {
          id: "frm_general",
          sessionID: "ses_x",
          title: "Questions",
          metadata: { tool: { messageID: "msg_plain" } },
          fields: [{ key: "q0", title: "Q", type: "string" }],
        },
      },
    })
    await new Promise((resolve) => setTimeout(resolve, 20))
    // Only the recorder status write happens; no form or answer is written for
    // a form the plugin did not present.
    expect(payloads.map((payload) => payload.action)).toEqual(["status"])
  })

  test("a session-less context disables recording without throwing", async () => {
    const logs: string[] = []
    const plugin = createDesignHistoryPlugin({ checkout: "", log: (message) => logs.push(message) })
    await plugin.setup({ location: {} })
    expect(logs[0]).toContain("recording is disabled")
  })
})
