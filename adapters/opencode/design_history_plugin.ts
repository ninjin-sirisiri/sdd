import { fileURLToPath } from "node:url"

type JsonRecord = Record<string, unknown>

/** One design question as the plugin presents it and as the store keeps it. */
export type DesignQuestion = {
  /** Stable question ID chosen by the caller; survives re-presentation. */
  questionID?: string
  text: string
  header?: string
  description?: string
  options?: Array<{ value?: string; label: string; description?: string }>
  allowsFreeText?: boolean
  required?: boolean
}

/** A form the plugin itself presented, bound to one design case and checkout. */
export type DesignRegistration = {
  case: string
  checkout: string
  sessionID: string
  formID: string
  title: string
  questions: Array<Required<Pick<DesignQuestion, "questionID" | "text">> & DesignQuestion & {
    fieldKey: string
    ordinal: number
  }>
  correlation: string
}

export type PendingPresentation = {
  correlation: string
  case: string
  checkout: string
  sessionID: string
  title: string
  questions: DesignQuestion[]
  createdAt: number
}

export type FormEvent = {
  type: string
  id?: string
  location?: { directory?: string }
  data?: JsonRecord
}

export type RecorderPayload = JsonRecord
export type RecorderResult = {
  ok: boolean
  status?: string
  detail?: string
  action?: string
  recorded?: string[]
  omitted?: string[]
  unanswered?: string[]
  questions?: number
}
export type Recorder = (payload: RecorderPayload) => Promise<RecorderResult>

export type EventStream = AsyncIterable<unknown>

export type HostToolContext = {
  sessionID: string
  messageID: string
  agent?: string
  directory?: string
  worktree?: string
  abort?: AbortSignal
  metadata?: (input: unknown) => void
  ask?: (input: unknown) => Promise<void>
  [key: string]: unknown
}

export type HostTool = {
  name: string
  description?: string
  input?: unknown
  output?: unknown
  execute(input: unknown, context: HostToolContext): Promise<unknown>
}

export type ToolRegistry = {
  get(name: string): HostTool | undefined
  add(tool: HostTool): unknown
  list?(): HostTool[]
  [key: string]: unknown
}

export type V2Context = {
  location?: { directory?: string }
  event?: { subscribe(options?: { types?: string[] }): EventStream }
  tool?: {
    transform(callback: (registry: ToolRegistry) => ToolRegistry | void): Promise<unknown>
    list?(): Promise<HostTool[]>
  }
  permission?: {
    hook(
      name: string,
      callback: (input: JsonRecord) => JsonRecord | void | Promise<JsonRecord | void>,
    ): Promise<unknown>
  }
  [key: string]: unknown
}

export const PLUGIN_ID = "sdd-design-history"
export const DESIGN_TOOL_NAME = "design_question"
const CORRELATION_PREFIX = "sdd_design:"
const PENDING_TTL_MS = 6 * 60 * 60 * 1000
const MAX_PENDING = 256
const WRITE_TIMEOUT_MS = 8_000
const WRITE_POLL_MS = 40

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function requireString(value: unknown, label: string): string {
  if (typeof value !== "string" || value.length === 0) {
    throw new Error(`${label} must be a non-empty string`)
  }
  return value
}

/** Outcome of writing one form's creation or settlement to the store. */
export type WriteOutcome = {
  ok: boolean
  detail?: string
}

export type FormWriteState = {
  created?: WriteOutcome
  settled?: WriteOutcome
}

/**
 * Registration table for design forms.
 *
 * `pending` holds a presentation the plugin started, keyed by the correlation
 * token the plugin put into the host message ID. `forms` holds confirmed
 * registrations keyed by the host's session + form ID. An answer is written only
 * when it matches `forms`, so an unrelated form can never become design
 * history even if it arrives in the same session.
 */
export type RegistrationTable = {
  addPending(pending: PendingPresentation): void
  takePending(correlation: string): PendingPresentation | undefined
  register(registration: DesignRegistration): void
  lookup(sessionID: string, formID: string): DesignRegistration | undefined
  lookupByCorrelation(correlation: string): DesignRegistration | undefined
  forget(sessionID: string, formID: string): void
  noteCreated(correlation: string, outcome: WriteOutcome): void
  noteSettled(sessionID: string, formID: string, outcome: WriteOutcome): void
  writeState(correlation: string): FormWriteState | undefined
  pendingCount(): number
  confirmedCount(): number
  prune(now: number): number
}

export function createRegistrationTable(options: { ttlMs?: number; limit?: number } = {}): RegistrationTable {
  const ttlMs = options.ttlMs ?? PENDING_TTL_MS
  const limit = options.limit ?? MAX_PENDING
  const pending = new Map<string, PendingPresentation>()
  const forms = new Map<string, DesignRegistration>()
  const byCorrelation = new Map<string, DesignRegistration>()
  const states = new Map<string, FormWriteState>()
  const key = (sessionID: string, formID: string) => `${sessionID}\u0000${formID}`

  const stateFor = (correlation: string): FormWriteState => {
    const existing = states.get(correlation)
    if (existing) return existing
    const created: FormWriteState = {}
    states.set(correlation, created)
    return created
  }

  const prune = (now: number): number => {
    let removed = 0
    for (const [correlation, entry] of pending) {
      if (now - entry.createdAt > ttlMs) {
        pending.delete(correlation)
        removed += 1
      }
    }
    if (pending.size > limit) {
      const ordered = [...pending.entries()].sort((left, right) => left[1].createdAt - right[1].createdAt)
      for (const [correlation] of ordered.slice(0, pending.size - limit)) {
        pending.delete(correlation)
        removed += 1
      }
    }
    return removed
  }

  return {
    addPending(entry) {
      pending.set(entry.correlation, entry)
      prune(Date.now())
    },
    takePending(correlation) {
      const entry = pending.get(correlation)
      if (entry === undefined) return undefined
      pending.delete(correlation)
      return entry
    },
    register(registration) {
      forms.set(key(registration.sessionID, registration.formID), registration)
      byCorrelation.set(registration.correlation, registration)
    },
    lookup(sessionID, formID) {
      return forms.get(key(sessionID, formID))
    },
    lookupByCorrelation(correlation) {
      return byCorrelation.get(correlation)
    },
    forget(sessionID, formID) {
      forms.delete(key(sessionID, formID))
    },
    noteCreated(correlation, outcome) {
      stateFor(correlation).created = outcome
    },
    noteSettled(sessionID, formID, outcome) {
      const registration = forms.get(key(sessionID, formID))
      if (!registration) return
      stateFor(registration.correlation).settled = outcome
    },
    writeState(correlation) {
      return states.get(correlation)
    },
    pendingCount() {
      return pending.size
    },
    confirmedCount() {
      return forms.size
    },
    prune,
  }
}

/**
 * The correlation token travels in the host message ID, so it survives into
 * `form.created` metadata (`metadata.tool.messageID`). It is the only signal
 * that ties a host form to the plugin's own presentation.
 */
export function correlationFromMessageID(messageID: string): string | undefined {
  if (!messageID.startsWith(CORRELATION_PREFIX)) return undefined
  const token = messageID.slice(CORRELATION_PREFIX.length)
  return token.length >= 8 ? token : undefined
}

export function messageIDFor(correlation: string): string {
  return `${CORRELATION_PREFIX}${correlation}`
}

/** A readable question ID that stays stable across re-presentation. */
export function questionIDFor(caseID: string, question: DesignQuestion, ordinal: number): string {
  const explicit = question.questionID?.trim()
  if (explicit) return explicit
  // Letters and digits from any script stay readable; punctuation collapses so
  // the ID is stable across whitespace and formatting changes.
  const slug = question.text
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40)
  return `${caseID}.q${ordinal + 1}${slug ? `-${slug}` : ""}`
}

/**
 * Build the host question-tool payload. Options keep presentation order; the
 * host renders each label and returns the selected label as the value, which is
 * exactly what the store records.
 */
export function buildHostQuestions(questions: DesignQuestion[]): JsonRecord[] {
  if (!Array.isArray(questions) || questions.length === 0) {
    throw new Error("a design presentation requires at least one question")
  }
  return questions.map((question, ordinal) => {
    const text = requireString(question.text, `questions[${ordinal}].text`)
    const options = (question.options ?? []).map((option, optionIndex) => {
      const label = requireString(option.label, `questions[${ordinal}].options[${optionIndex}].label`)
      return {
        label,
        ...(option.description ? { description: option.description } : {}),
      }
    })
    return {
      question: text,
      header: question.header ?? `Q${ordinal + 1}`,
      // The host requires an options array even when free text is allowed; it
      // appends its own free-text choice to the presented form.
      options,
    }
  })
}

/** Field key the host assigns, in presentation order (`q0`, `q1`, …). */
export function fieldKeyFor(ordinal: number): string {
  return `q${ordinal}`
}

export function registrationFromCreatedEvent(
  event: FormEvent,
  table: RegistrationTable,
  checkout: string,
): DesignRegistration | undefined {
  if (event.type !== "form.created" || !isRecord(event.data)) return undefined
  const form = event.data.form
  if (!isRecord(form)) return undefined
  const formID = form.id
  const sessionID = form.sessionID
  if (typeof formID !== "string" || typeof sessionID !== "string") return undefined
  const metadata = isRecord(form.metadata) ? form.metadata : {}
  const tool = isRecord(metadata.tool) ? metadata.tool : {}
  const messageID = typeof tool.messageID === "string" ? tool.messageID : ""
  const correlation = correlationFromMessageID(messageID)
  if (!correlation) return undefined
  const pending = table.takePending(correlation)
  if (!pending) return undefined
  if (pending.sessionID !== sessionID) return undefined

  const fields = Array.isArray(form.fields) ? form.fields : []
  const questions = pending.questions.map((question, ordinal) => {
    const field = isRecord(fields[ordinal]) ? fields[ordinal] : undefined
    const hostKey = field && typeof field.key === "string" ? field.key : fieldKeyFor(ordinal)
    // The host may reorder or relabel options; the presented labels stay the
    // reference, and the host's field key is kept for reply correlation.
    return {
      ...question,
      questionID: questionIDFor(pending.case, question, ordinal),
      fieldKey: hostKey,
      ordinal,
    }
  })
  const registration: DesignRegistration = {
    case: pending.case,
    checkout: pending.checkout || checkout,
    sessionID,
    formID,
    title: pending.title,
    questions,
    correlation,
  }
  table.register(registration)
  return registration
}

export function registerPayload(registration: DesignRegistration, source = "opencode.form.created"): RecorderPayload {
  return {
    action: "register",
    checkout: registration.checkout,
    sessionID: registration.sessionID,
    formID: registration.formID,
    case: registration.case,
    title: registration.title,
    source,
    metadata: { host: "opencode-v2", correlation: registration.correlation },
    questions: registration.questions.map((question) => ({
      questionID: question.questionID,
      fieldKey: question.fieldKey,
      ordinal: question.ordinal,
      text: question.text,
      header: question.header,
      description: question.description,
      options: question.options ?? [],
      allowsFreeText: question.allowsFreeText !== false,
      required: question.required === true,
    })),
  }
}

export function identifiersFromEvent(event: FormEvent): { sessionID: string; formID: string } | undefined {
  if (!isRecord(event.data)) return undefined
  const formID = event.data.id
  const sessionID = event.data.sessionID
  if (typeof formID !== "string" || typeof sessionID !== "string") return undefined
  return { sessionID, formID }
}

/**
 * Translate the host answer map (`q0` → value) into the stable question IDs the
 * plugin registered. Unknown keys are returned so the store can note them
 * rather than inventing answers.
 */
export function answerMapForRegistration(
  registration: DesignRegistration,
  answers: JsonRecord,
): { answers: JsonRecord; unknown: string[] } {
  const byField = new Map(registration.questions.map((question) => [question.fieldKey, question.questionID]))
  const byID = new Set(registration.questions.map((question) => question.questionID))
  const mapped: JsonRecord = {}
  const unknown: string[] = []
  for (const [key, value] of Object.entries(answers)) {
    const questionID = byField.get(key)
    if (questionID !== undefined) {
      mapped[questionID] = value
    } else if (byID.has(key)) {
      mapped[key] = value
    } else {
      unknown.push(key)
    }
  }
  return { answers: mapped, unknown }
}

/** Only events whose checkout matches the registration may be written. */
export function eventBelongsToCheckout(event: FormEvent, registration: DesignRegistration): boolean {
  const directory = event.location?.directory
  if (typeof directory !== "string" || directory.length === 0) return true
  const normalize = (value: string) => value.replace(/\/+$/, "")
  return normalize(directory) === normalize(registration.checkout)
}

export type HandlerOptions = {
  checkout: string
  recorder: Recorder
  registrations: RegistrationTable
  log?: (message: string) => void
  seenEvents?: Set<string>
}

/**
 * Handle one host event. Returns the recorder result when something was
 * written, otherwise undefined. A form the plugin did not present is ignored:
 * its answer must never be recorded as a design answer.
 */
export async function handleFormEvent(
  event: FormEvent,
  options: HandlerOptions,
): Promise<RecorderResult | undefined> {
  const { recorder, registrations } = options

  if (event.type === "form.created") {
    const registration = registrationFromCreatedEvent(event, registrations, options.checkout)
    if (!registration) return undefined
    const result = await recorder(registerPayload(registration))
    registrations.noteCreated(registration.correlation, {
      ok: result.ok !== false,
      detail: result.detail,
    })
    return result
  }

  if (event.type !== "form.replied" && event.type !== "form.cancelled") return undefined
  const identifiers = identifiersFromEvent(event)
  if (!identifiers) return undefined
  const registration = registrations.lookup(identifiers.sessionID, identifiers.formID)
  if (!registration) return undefined
  if (!eventBelongsToCheckout(event, registration)) {
    options.log?.(
      `design history: ignoring ${event.type} for ${identifiers.formID} from another checkout`,
    )
    return undefined
  }
  if (event.id && options.seenEvents?.has(event.id)) return undefined
  if (event.id) options.seenEvents?.add(event.id)

  if (event.type === "form.cancelled") {
    const result = await recorder({
      action: "cancel",
      checkout: registration.checkout,
      sessionID: identifiers.sessionID,
      formID: identifiers.formID,
      case: registration.case,
      source: "opencode.form.cancelled",
      delivery: "event",
      eventID: event.id,
    })
    registrations.noteSettled(identifiers.sessionID, identifiers.formID, {
      ok: result.ok !== false,
      detail: result.detail,
    })
    return result
  }

  const raw = isRecord(event.data) && isRecord(event.data.answer) ? event.data.answer : undefined
  if (!raw) return undefined
  const { answers } = answerMapForRegistration(registration, raw)
  const result = await recorder({
    action: "reply",
    checkout: registration.checkout,
    sessionID: identifiers.sessionID,
    formID: identifiers.formID,
    case: registration.case,
    answers,
    recordMissing: true,
    source: "opencode.form.replied",
    delivery: "event",
    eventID: event.id,
  })
  registrations.noteSettled(identifiers.sessionID, identifiers.formID, {
    ok: result.ok !== false,
    detail: result.detail,
  })
  return result
}

export function newCorrelation(): string {
  const bytes = new Uint8Array(12)
  crypto.getRandomValues(bytes)
  return [...bytes].map((byte) => byte.toString(16).padStart(2, "0")).join("")
}

export type DesignQuestionToolOptions = {
  checkout: string
  recorder: Recorder
  registrations: RegistrationTable
  findQuestionTool: () => Promise<HostTool | undefined>
  log?: (message: string) => void
  now?: () => number
  correlation?: () => string
  writeTimeoutMs?: number
}

export type DesignQuestionToolInput = {
  case?: unknown
  title?: unknown
  questions?: unknown
}

function normalizeToolQuestions(value: unknown): DesignQuestion[] {
  if (!Array.isArray(value) || value.length === 0) {
    throw new Error("questions must be a non-empty array")
  }
  return value.map((entry, index) => {
    if (!isRecord(entry)) throw new Error(`questions[${index}] must be an object`)
    const text = requireString(entry.text ?? entry.question, `questions[${index}].text`)
    const optionsRaw = entry.options
    const options = Array.isArray(optionsRaw)
      ? optionsRaw.map((option, optionIndex) => {
        if (!isRecord(option)) throw new Error(`questions[${index}].options[${optionIndex}] must be an object`)
        const label = requireString(
          option.label ?? option.value,
          `questions[${index}].options[${optionIndex}].label`,
        )
        return {
          label,
          ...(typeof option.description === "string" && option.description
            ? { description: option.description }
            : {}),
        }
      })
      : []
    return {
      questionID: typeof entry.id === "string" && entry.id ? entry.id : undefined,
      text,
      ...(typeof entry.header === "string" && entry.header ? { header: entry.header } : {}),
      ...(typeof entry.description === "string" && entry.description
        ? { description: entry.description }
        : {}),
      options,
      allowsFreeText: entry.allowsFreeText !== false,
      required: entry.required === true,
    }
  })
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * Declared output schema for the design tool.
 *
 * OpenCode's dispatcher crashes on a bare-string tool return (`"output" in a`)
 * and rejects `{ output }` without a declared schema ("Tool result declared
 * output without an output schema"). Both were observed on 2.2.7 with a real
 * model call. Declaring a plain JSON Schema as the output keeps the
 * acknowledgement a `{ output: string }` object, like the built-in question
 * tool. A `~standard`-shaped schema is deliberately avoided: the host expects
 * its `jsonSchema` member to be a map of functions, and a wrong shape there is
 * rejected at registration with "Skipping invalid tool registration".
 */
const OUTPUT_SCHEMA = { type: "string" }

function acknowledgement(message: string): { output: string } {
  return { output: message }
}

/**
 * The plugin-published design tool. It presents the questions through the
 * host's native question/form tool and returns only an acknowledgement. The
 * answer values never pass back through the model, so the model cannot become a
 * transcription path for design history.
 */
export function createDesignQuestionTool(options: DesignQuestionToolOptions): HostTool {
  const now = options.now ?? (() => Date.now())
  const correlation = options.correlation ?? newCorrelation
  const writeTimeoutMs = options.writeTimeoutMs ?? WRITE_TIMEOUT_MS
  return {
    name: DESIGN_TOOL_NAME,
    description:
      "Present an SDD design interview as a native form. Arguments: `case` (the design " +
      "case ID, a non-empty string), `title` (optional form title), and `questions` " +
      "(a non-empty array of { text, header?, description?, options?: [{ label, " +
      "description? }], allowsFreeText?, required? }). Options are shown in array " +
      "order. Each question becomes one field; separate decisions use separate " +
      "questions. The user's answer is recorded as design history for this checkout; " +
      "the result summarizes only whether the recording succeeded and never repeats " +
      "the answer values.",
    input: undefined,
    output: OUTPUT_SCHEMA,
    async execute(rawInput: unknown, context: HostToolContext): Promise<{ output: string }> {
      const input: DesignQuestionToolInput = isRecord(rawInput) ? rawInput : {}
      const caseID = requireString(input.case, "case")
      const questions = normalizeToolQuestions(input.questions)
      const title =
        typeof input.title === "string" && input.title
          ? input.title
          : `Design interview: ${caseID}`
      const token = correlation()
      const pending: PendingPresentation = {
        correlation: token,
        case: caseID,
        checkout: options.checkout,
        sessionID: context.sessionID,
        title,
        questions,
        createdAt: now(),
      }
      options.registrations.addPending(pending)

      const hostTool = await options.findQuestionTool()
      if (!hostTool) {
        options.registrations.takePending(token)
        options.log?.("design history: the host question tool is unavailable; nothing was recorded")
        return acknowledgement(
          "The host does not provide a native question form, so no design answer was recorded.",
        )
      }

      let result: unknown
      try {
        result = await hostTool.execute(
          { questions: buildHostQuestions(questions) },
          { ...context, messageID: messageIDFor(token) },
        )
      } catch (error) {
        // The host cancelled the form, or the agent's permission rules denied
        // it. Draining the pending entry keeps the table small; a
        // form.cancelled event records the state if it arrives. The message
        // tells the model which happened so it does not report a denial as an
        // answer the person declined to give.
        options.registrations.takePending(token)
        const message = error instanceof Error ? error.message : String(error)
        options.log?.(`design history: the form was not answered: ${message}`)
        if (/permission denied/i.test(message)) {
          return acknowledgement(
            "The host denied the question permission, so the design form was never shown " +
            "and no answer was recorded. The agent's permission rules must allow the " +
            "`question` action for design history to work.",
          )
        }
        return acknowledgement(
          "The question form was cancelled or failed, so no design answer was recorded.",
        )
      }

      // Wait for the plugin's own event handlers to finish the store writes.
      // The tool must not claim a recording before the store accepted it.
      const deadline = now() + writeTimeoutMs
      let state = options.registrations.writeState(token)
      while (now() < deadline && !(state?.created && state?.settled)) {
        await delay(WRITE_POLL_MS)
        state = options.registrations.writeState(token)
      }

      if (!state?.created) {
        options.registrations.takePending(token)
        options.log?.("design history: the host form creation event was lost; the answer was not recorded")
        return acknowledgement(
          "The form was answered, but the host did not publish its creation event, so the " +
          "answer could not be correlated and was not recorded. Re-ask in a new session and " +
          "report the missing recording before relying on this answer.",
        )
      }
      if (!state.created.ok) {
        return acknowledgement(
          "The form was answered, but the design history write failed, so the answer was not " +
          `recorded (${state.created.detail ?? "unknown store error"}). Run the design-history ` +
          "status command, fix the reported cause, and re-ask before relying on this answer.",
        )
      }
      if (!state.settled) {
        return acknowledgement(
          "The form was answered and the question was registered, but the answer write did not " +
          "complete, so the answer may not be recorded. Check the design-history status command " +
          "before relying on this answer.",
        )
      }
      if (!state.settled.ok) {
        return acknowledgement(
          "The form was answered, but the answer write failed, so the answer was not recorded " +
          `(${state.settled.detail ?? "unknown store error"}). Run the design-history status ` +
          "command, fix the reported cause, and re-ask before relying on this answer.",
        )
      }

      return acknowledgement(summarizeHostResult(result))
    },
  }
}

/**
 * Summarize the host result without repeating the answer text. Returning the
 * answers to the model would make the model a transcription path for history.
 */
export function summarizeHostResult(result: unknown): string {
  const answers = isRecord(result) && isRecord(result.output) && Array.isArray(result.output.answers)
    ? result.output.answers
    : undefined
  if (!answers) {
    return "The design question form was answered and recorded in the design history. The answer values are intentionally not repeated here."
  }
  const answered = answers.filter((entry) => Array.isArray(entry) && entry.length > 0).length
  return `The design question form was answered and recorded in the design history (${answered}/${answers.length} questions). The answer values are intentionally not repeated here.`
}

/** Recorder that shells out to the pack's `scripts/design-history record`. */
export function createCliRecorder(checkout: string, cliPath?: string): Recorder {
  const cli = cliPath
    ?? process.env.SDD_DESIGN_HISTORY_CLI
    ?? fileURLToPath(new URL("../../scripts/design-history", import.meta.url))
  const python = process.env.SDD_PYTHON || "python3"
  return async (payload) => {
    const child = Bun.spawn([python, cli, "record"], {
      cwd: checkout,
      stdin: "pipe",
      stdout: "pipe",
      stderr: "pipe",
    })
    child.stdin.write(JSON.stringify(payload))
    child.stdin.end()
    const exitCode = await child.exited
    const output = await new Response(child.stdout).text()
    const error = await new Response(child.stderr).text()
    if (exitCode !== 0) {
      return {
        ok: false,
        status: "error",
        detail: `design-history record exited ${exitCode}: ${(error || output).trim()}`,
      }
    }
    try {
      const parsed: unknown = JSON.parse(output)
      if (!isRecord(parsed)) return { ok: false, detail: "design-history returned a non-object result" }
      return parsed as RecorderResult
    } catch (parseError) {
      return { ok: false, detail: `design-history returned invalid JSON: ${String(parseError)}` }
    }
  }
}

export type DesignHistoryPluginOverrides = {
  recorder?: Recorder
  registrations?: RegistrationTable
  log?: (message: string) => void
  now?: () => number
  correlation?: () => string
  checkout?: string
  writeTimeoutMs?: number
}

export type DesignHistoryPlugin = {
  id: string
  setup(context: V2Context): Promise<void>
}

/**
 * OpenCode V2 requires a default-exported `{ id, setup }` object; a named
 * function export is silently ignored. The plugin registers the design tool,
 * observes the host's question permission decision, records that recording is
 * active, and subscribes to form events. `subscribe()` also delivers unrelated
 * server events, so every event is filtered on `event.type`.
 */
export function createDesignHistoryPlugin(overrides: DesignHistoryPluginOverrides = {}): DesignHistoryPlugin {
  return {
    id: PLUGIN_ID,
    async setup(context) {
      const checkout = overrides.checkout ?? context.location?.directory
      const log = overrides.log ?? ((message: string) => {
        try {
          process.stderr.write(`${message}\n`)
        } catch {
          // A closed stderr must not break the host plugin.
        }
      })
      if (typeof checkout !== "string" || checkout.length === 0) {
        log("design history: no checkout directory; recording is disabled")
        return
      }
      const registrations = overrides.registrations ?? createRegistrationTable()
      const recorder = overrides.recorder ?? createCliRecorder(checkout)
      const seenEvents = new Set<string>()
      const handlerOptions: HandlerOptions = { checkout, recorder, registrations, log, seenEvents }

      // Record that the hook is running. This is what distinguishes "recording
      // is active but nothing matched" from "the hook never ran".
      await recorder({ action: "status", checkout, status: "active", source: "opencode.plugin" })
        .then((result) => {
          if (result.ok === false) {
            log(`design history: recording is not active: ${result.detail ?? "store refused the write"}`)
          }
        })
        .catch((error: unknown) => {
          log(`design history: recording is not active: ${stopMessage(error)}`)
        })

      const findQuestionTool = async (): Promise<HostTool | undefined> => {
        const listed = await context.tool?.list?.()
        if (Array.isArray(listed)) {
          const found = listed.find(
            (tool) => (tool.name ?? (tool as { id?: string }).id) === "question",
          )
          if (found) return found
        }
        let discovered: HostTool | undefined
        await context.tool?.transform((registry) => {
          discovered = registry.get("question")
          return registry
        })
        return discovered
      }

      try {
        await context.tool?.transform((registry) => {
          if (!registry.get(DESIGN_TOOL_NAME)) {
            registry.add(
              createDesignQuestionTool({
                checkout,
                recorder,
                registrations,
                findQuestionTool,
                log,
                now: overrides.now,
                correlation: overrides.correlation,
                writeTimeoutMs: overrides.writeTimeoutMs,
              }),
            )
          }
          return registry
        })
      } catch (error) {
        log(`design history: could not register the design question tool: ${stopMessage(error)}`)
      }

      // The host gates its question tool behind a permission decision. This hook
      // is informative only: on opencode 2.2.7 `PluginHooks.trigger` runs the
      // callbacks and then returns the original input, so a returned `effect`
      // does not grant anything. Whether a question may be asked is decided by
      // the agent's configured permissions; when the agent denies `question`,
      // the host tool throws `Permission denied: question` and the adapter
      // reports a cancellation instead of inventing a recording.
      try {
        await context.permission?.hook("evaluate", (input) => {
          if (isRecord(input) && input.action === "question") {
            log("design history: the host is evaluating a design question permission")
          }
          return undefined
        })
      } catch (error) {
        log(`design history: could not attach the question permission hook: ${stopMessage(error)}`)
      }

      const stream = context.event?.subscribe({ types: ["form.created", "form.replied", "form.cancelled"] })
      if (!stream) {
        log("design history: the host does not expose form events; recording is disabled")
        return
      }
      // Events are handled in arrival order: form.created must register the form
      // before form.replied looks it up.
      let queue: Promise<void> = Promise.resolve()
      ;(async () => {
        try {
          for await (const raw of stream) {
            if (!isRecord(raw) || typeof raw.type !== "string" || !raw.type.startsWith("form.")) continue
            const event = raw as FormEvent
            queue = queue.then(async () => {
              try {
                await handleFormEvent(event, handlerOptions)
              } catch (error) {
                log(`design history: failed to record ${event.type}: ${stopMessage(error)}`)
              }
            })
          }
        } catch (error) {
          log(`design history: event stream ended: ${stopMessage(error)}`)
        }
      })()
    },
  }
}

function stopMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

const plugin = createDesignHistoryPlugin()
export default plugin
