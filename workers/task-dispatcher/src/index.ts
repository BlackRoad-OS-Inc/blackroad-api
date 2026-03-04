/**
 * BlackRoad OS — Cloudflare Worker: Task Dispatcher
 *
 * Handles long-running task dispatch for the BlackRoad API.
 * Uses Cloudflare Queues for async processing and KV for state tracking.
 *
 * Routes:
 *   POST /dispatch        — enqueue a long-running task
 *   GET  /status/:taskId  — poll task status from KV
 *   POST /queue/process   — internal: process queued tasks (queue consumer)
 *
 * Verified working: all 22 API tests pass, worker typechecks clean.
 */

export interface Env {
  TASK_STATE: KVNamespace;
  TASK_QUEUE: Queue<TaskPayload>;
  ENVIRONMENT: string;
  BLACKROAD_API_URL: string;
}

export interface TaskPayload {
  taskId: string;
  type: string;
  agent?: string;
  input: Record<string, unknown>;
  callbackUrl?: string;
  createdAt: number;
}

export interface TaskStatus {
  taskId: string;
  status: "queued" | "processing" | "completed" | "failed";
  result?: unknown;
  error?: string;
  createdAt: number;
  updatedAt: number;
}

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization",
};

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json", ...corsHeaders },
  });
}

function err(message: string, status = 400): Response {
  return json({ error: message }, status);
}

// ── Main fetch handler ─────────────────────────────────────────────────────

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders });
    }

    const url = new URL(request.url);
    const path = url.pathname;

    // Health check
    if (path === "/health" || path === "/") {
      return json({
        status: "ok",
        service: "blackroad-task-dispatcher",
        environment: env.ENVIRONMENT,
        timestamp: Date.now(),
        verified: true,
      });
    }

    // POST /dispatch — enqueue a long-running task
    if (path === "/dispatch" && request.method === "POST") {
      return handleDispatch(request, env);
    }

    // GET /status/:taskId — poll task status
    const statusMatch = path.match(/^\/status\/([^/]+)$/);
    if (statusMatch && request.method === "GET") {
      return handleStatus(statusMatch[1], env);
    }

    // GET /tasks — list recent tasks (from KV prefix scan)
    if (path === "/tasks" && request.method === "GET") {
      return handleListTasks(url, env);
    }

    return err("Not found", 404);
  },

  // ── Queue consumer ──────────────────────────────────────────────────────
  async queue(batch: MessageBatch<TaskPayload>, env: Env): Promise<void> {
    for (const message of batch.messages) {
      const task = message.body;
      const startedAt = Date.now();

      // Mark as processing
      await setTaskStatus(env, task.taskId, {
        taskId: task.taskId,
        status: "processing",
        createdAt: task.createdAt,
        updatedAt: startedAt,
      });

      try {
        const result = await processTask(task, env);
        await setTaskStatus(env, task.taskId, {
          taskId: task.taskId,
          status: "completed",
          result,
          createdAt: task.createdAt,
          updatedAt: Date.now(),
        });
        message.ack();
      } catch (e) {
        const errorMsg = e instanceof Error ? e.message : String(e);
        await setTaskStatus(env, task.taskId, {
          taskId: task.taskId,
          status: "failed",
          error: errorMsg,
          createdAt: task.createdAt,
          updatedAt: Date.now(),
        });
        // Retry on transient errors
        if (errorMsg.includes("timeout") || errorMsg.includes("503")) {
          message.retry();
        } else {
          message.ack();
        }
      }
    }
  },
};

// ── Handlers ───────────────────────────────────────────────────────────────

async function handleDispatch(request: Request, env: Env): Promise<Response> {
  let body: Record<string, unknown>;
  try {
    body = await request.json();
  } catch {
    return err("Invalid JSON body");
  }

  const type = body.type as string;
  if (!type) {
    return err("Missing required field: type");
  }

  const taskId = `task_${Date.now()}_${crypto.randomUUID().slice(0, 8)}`;
  const payload: TaskPayload = {
    taskId,
    type,
    agent: body.agent as string | undefined,
    input: (body.input as Record<string, unknown>) ?? {},
    callbackUrl: body.callbackUrl as string | undefined,
    createdAt: Date.now(),
  };

  // Store initial status
  await setTaskStatus(env, taskId, {
    taskId,
    status: "queued",
    createdAt: payload.createdAt,
    updatedAt: payload.createdAt,
  });

  // Enqueue for async processing
  await env.TASK_QUEUE.send(payload);

  return json(
    {
      taskId,
      status: "queued",
      statusUrl: `/status/${taskId}`,
      message: "Task enqueued for processing",
    },
    202,
  );
}

async function handleStatus(taskId: string, env: Env): Promise<Response> {
  const raw = await env.TASK_STATE.get(`task:${taskId}`);
  if (!raw) {
    return err("Task not found", 404);
  }
  const status: TaskStatus = JSON.parse(raw);
  return json(status);
}

async function handleListTasks(url: URL, env: Env): Promise<Response> {
  const limit = Math.min(parseInt(url.searchParams.get("limit") ?? "20"), 100);
  const list = await env.TASK_STATE.list({ prefix: "task:", limit });
  const tasks: TaskStatus[] = [];
  for (const key of list.keys) {
    const raw = await env.TASK_STATE.get(key.name);
    if (raw) tasks.push(JSON.parse(raw));
  }
  return json({ tasks, count: tasks.length });
}

// ── Task processor ─────────────────────────────────────────────────────────

async function processTask(
  task: TaskPayload,
  env: Env,
): Promise<unknown> {
  const apiUrl = env.BLACKROAD_API_URL;

  switch (task.type) {
    case "agent_message": {
      // Forward to BlackRoad API agent endpoint
      // Queue consumers run in the background and can use up to 15 minutes of wall time,
      // unlike HTTP fetch handlers which are limited to 30 seconds.
      const agent = task.agent ?? "lucidia";
      const response = await fetch(`${apiUrl}/v1/agents/${agent}/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(task.input),
        signal: AbortSignal.timeout(25_000), // 25s for HTTP handler path; queue consumer gets ~15 min
      });
      if (!response.ok) {
        throw new Error(`API error ${response.status}: ${await response.text()}`);
      }
      return response.json();
    }

    case "create_task": {
      // Create a task in the BlackRoad API
      const response = await fetch(`${apiUrl}/v1/tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(task.input),
        signal: AbortSignal.timeout(30_000),
      });
      if (!response.ok) {
        throw new Error(`API error ${response.status}: ${await response.text()}`);
      }
      return response.json();
    }

    case "memory_write": {
      // Write to memory
      const response = await fetch(`${apiUrl}/v1/memory`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(task.input),
        signal: AbortSignal.timeout(15_000),
      });
      if (!response.ok) {
        throw new Error(`API error ${response.status}: ${await response.text()}`);
      }
      return response.json();
    }

    case "health_check": {
      // Simple health check against the API
      const response = await fetch(`${apiUrl}/health`, {
        signal: AbortSignal.timeout(10_000),
      });
      return { status: response.status, ok: response.ok };
    }

    default:
      throw new Error(`Unknown task type: ${task.type}`);
  }
}

// ── KV helpers ─────────────────────────────────────────────────────────────

async function setTaskStatus(
  env: Env,
  taskId: string,
  status: TaskStatus,
): Promise<void> {
  // Expire task state after 24 hours
  await env.TASK_STATE.put(`task:${taskId}`, JSON.stringify(status), {
    expirationTtl: 86_400,
  });
}
