// tests/js/frontend_smoke.test.js
//
// 前端冒烟测试：以"真实执行 index.html 里的 JavaScript"的方式，验证页面能启动并拉到数据。
//
// ── 为什么必须有这个测试 ─────────────────────────────────────────────
// 此前所有测试都用 Flask 的 test_client，它只执行 Python、**从不执行 JavaScript**。
// 后果：一个从 v0.1.0 就存在的前端崩溃（api() 里 && 与 || 混用导致 GET 请求抛
// TypeError，请求根本没发出去，页面显示"加载失败"）在 39 个测试全绿的情况下存活了
// 很久，直到用户在浏览器里亲自打开才发现。
// 这个文件就是用来堵这个盲区的：它真的把页面脚本跑起来。
//
// ── 运行方式（两种都支持）────────────────────────────────────────────
//   node tests/js/frontend_smoke.test.js   # 直接运行（自带极简框架，任何环境可用）
//   node --test tests/js/                  # Node 内置测试框架（CI 使用）
//
// 注意：受限沙箱里 `node --test` 会因需要派生子进程而报 EPERM，
// 因此这里刻意写成"直接运行也能用"，保证本地与 CI 都能跑。
//
// ── 桩环境的一个关键点 ───────────────────────────────────────────────
// 页面脚本末尾的 bootstrap() 会**不 await** 地调用一次 load()。这意味着脚本一执行
// 就有一个后台请求在飞。若测试自己再调用 load()，两次执行会互相覆盖状态，产生随机
// 失败（本文件初版就踩了这个坑）。因此这里的约定是：
//   · 每个用例等它需要的那次请求真正结束后再断言（用 waitFor）
//   · 后端的最后一个请求处理完之前不关服务器（否则会刷出 ECONNREFUSED 噪音）

const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const vm = require("node:vm");
const { strict: assert } = require("node:assert");

const ROOT = path.join(__dirname, "..", "..");
const TEMPLATE = path.join(ROOT, "src", "question_notebook", "templates", "index.html");

// ── 测试运行器：优先用 Node 内置 node:test；没有就直接收集、自己跑 ──────────
let nodeTest = null;
try {
  nodeTest = require("node:test");
} catch (_) {
  nodeTest = null;
}
const collected = [];

/** 声明一个测试用例（两种运行方式下都工作）。 */
function suite(name, fn) {
  if (nodeTest) nodeTest(name, fn);
  else collected.push([name, fn]);
}

// ── 通用小工具 ───────────────────────────────────────────────────────

/** 轮询等待条件成立，超时抛错。用于等"后台那次请求"结束。 */
async function waitFor(predicate, message, timeoutMs = 3000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (predicate()) return;
    await new Promise((r) => setTimeout(r, 10));
  }
  throw new Error(`等待超时：${message}`);
}

/** 取出内联脚本，并把 Jinja 模板变量替换成合法 JS 字面量（模拟服务端渲染）。 */
function renderInlineScript(htmlPath = TEMPLATE) {
  const html = fs.readFileSync(htmlPath, "utf8");
  const m = html.match(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/i);
  assert.ok(m, "index.html 里应当存在内联 <script> 块");
  return m[1]
    .replace(/\{\{\s*csrf_token\s*\}\}/g, "TEST_TOKEN")
    .replace(/\{\{\s*auth_enabled\s*\}\}/g, "false")
    .replace(/\{\{\s*logged_in\s*\}\}/g, "true");
}

/**
 * 最小 DOM 桩：只实现被测脚本真正用到的接口。
 *
 * ⚠️ 关键细节：`<select>` 的默认值。
 *    浏览器里没有写 selected 的 <select>，其 .value 会自动等于**第一个 option 的值**
 *    （本项目里是 "all"）。若桩把 value 初始化成空字符串，过滤逻辑就会
 *    `cat !== 'all' && q.category !== cat` 把所有问题都滤掉，页面显示"空空如也"，
 *    从而让人误以为产品有 bug——实际是桩与浏览器的行为不一致。
 *    因此这里从真实 HTML 里把每个 <select> 的默认值读出来，保证桩的行为贴近浏览器。
 */
function makeDom(html) {
  const els = {};
  const mk = (id) => ({
    id,
    value: "",
    textContent: "",
    innerHTML: "",
    style: {},
    dataset: {},
    classList: { add() {}, remove() {}, contains: () => false },
    addEventListener() {},
    appendChild() {},
    querySelector: () => null,
    querySelectorAll: () => [],
  });

  // 从 HTML 里解析 <select id="x"> 的第一个 <option value="...">
  const selectDefaults = {};
  if (html) {
    for (const m of html.matchAll(/<select[^>]*\bid="([^"]+)"[^>]*>([\s\S]*?)<\/select>/gi)) {
      const id = m[1];
      const opt = m[2].match(/<option[^>]*\bvalue="([^"]*)"/i);
      if (opt) selectDefaults[id] = opt[1];
    }
  }

  return {
    els,
    selectDefaults,
    document: {
      getElementById: (id) => {
        if (!els[id]) {
          els[id] = mk(id);
          if (id in selectDefaults) els[id].value = selectDefaults[id]; // 模拟浏览器默认选中
        }
        return els[id];
      },
      querySelector: () => null,
      querySelectorAll: () => [],
      addEventListener: () => {},
      body: mk("body"),
    },
  };
}

/** 模拟后端：/api/questions 返回一条固定问题。 */
async function startBackend() {
  const requests = [];
  const server = http.createServer((req, res) => {
    requests.push(req.method + " " + req.url);
    if (req.url === "/api/questions") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify([
        {
          id: 1,
          title: "冒烟测试问题",
          description: "",
          timestamp: "2026-09-01 10:00:00",
          is_solved: false,
          solution: "",
          category: "未分类",
        },
      ]));
    } else if (req.url === "/api/stats") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({
        total: 1, solved: 0, open: 1, solve_rate: 0, by_category: [], by_month: [],
      }));
    } else {
      res.writeHead(404, { "Content-Type": "application/json" });
      res.end("{}");
    }
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address();
  return {
    baseUrl: `http://127.0.0.1:${port}`,
    requests,
    close: () => new Promise((r) => server.close(r)),
  };
}

/**
 * 执行页面脚本，返回执行环境。
 * script：要执行的源码（默认取模板里的真实脚本）
 * backend：若提供，fetch 走真实 HTTP；否则用内存桩
 * capture：每次 fetch 的 { url, method, headers } 会推入此数组（headers 深拷贝）
 */
function bootPage({ script, backend = null, capture = [] } = {}) {
  // 把真实 HTML 交给 DOM 桩，让它能还原 <select> 的浏览器默认值
  const dom = makeDom(fs.readFileSync(TEMPLATE, "utf8"));
  const sandbox = {
    console: { log() {}, error() {}, warn() {} },
    document: dom.document,
    window: { addEventListener: () => {}, location: { reload() {} } },
    sessionStorage: { getItem: () => null, setItem() {}, clear() {}, removeItem() {} },
    localStorage: { getItem: () => null, setItem() {}, clear() {} },
    setTimeout: () => 0,
    clearTimeout: () => {},
    FormData: class FormData {},
    fetch: async (url, opts) => {
      capture.push({
        url,
        method: (opts && opts.method) || "GET",
        headers: JSON.parse(JSON.stringify((opts && opts.headers) || {})),
      });
      if (backend) return fetch(backend.baseUrl + url, opts);
      return { status: 200, ok: true, json: async () => [] };
    },
  };
  sandbox.globalThis = sandbox;
  const ctx = vm.createContext(sandbox);
  // 执行脚本会触发 bootstrap() → 后台 load()（不 await），因此调用方需自行 waitFor
  vm.runInContext(script, ctx, { filename: "index.html-inline.js" });
  return { ctx, dom };
}

/**
 * 把"修复前"那段有 bug 的判断式替换回来，用于验证本测试确实能发现该 bug。
 * 修复后的代码把判断拆成了 hasBody / hasContentType 两个具名布尔量。
 */
function injectPreFixBug(script) {
  const fixed = script.match(/\/\/ 只有"带 body[\s\S]*?if \(hasBody && !hasContentType\) \{[\s\S]*?\n  \}/);
  assert.ok(fixed, "未能在页面脚本中定位修复后的判断式（测试需要随实现更新）");
  const buggy =
    'if (opts.body && !(opts.body instanceof FormData) &&\n' +
    "      !opts.headers || !Object.keys(opts.headers).some(k => k.toLowerCase() === 'content-type')) {\n" +
    "    headers['Content-Type'] = 'application/json';\n" +
    "  }";
  return script.replace(fixed[0], buggy);
}

// ── 用例 ─────────────────────────────────────────────────────────────

suite("页面脚本能被解析执行（无语法错误）", () => {
  const code = renderInlineScript();
  assert.doesNotThrow(() => new vm.Script(code), "内联脚本应能通过语法检查");
});

suite("页面启动后能拉到数据并渲染出问题列表（首屏可用）", async () => {
  const backend = await startBackend();
  const capture = [];
  try {
    const { dom } = bootPage({ script: renderInlineScript(), backend, capture });

    // 等首屏那次 load() 真正把标题渲染出来
    await waitFor(
      () => (dom.els["grid"] || {}).innerHTML && dom.els["grid"].innerHTML.includes("冒烟测试问题"),
      "首屏应渲染出后端返回的问题标题"
    );

    const gridHtml = dom.els["grid"].innerHTML;
    assert.ok(!gridHtml.includes("加载失败"), "页面不应显示加载失败提示");
    assert.ok(
      capture.some((c) => c.url === "/api/questions"),
      `必须真的请求 /api/questions。实际发出：${JSON.stringify(capture.map((c) => c.url))}`
    );
    assert.ok(
      backend.requests.some((x) => x.includes("/api/questions")),
      `服务端应收到 /api/questions，实际：${JSON.stringify(backend.requests)}`
    );
  } finally {
    await backend.close();
  }
});

suite("GET 请求不应被误加 Content-Type", async () => {
  const capture = [];
  const { ctx, dom } = bootPage({ script: renderInlineScript(), capture });

  // 等后台首屏请求结束，再用干净的状态做手势
  await waitFor(() => capture.length >= 1, "首屏请求应已发出");
  await vm.runInContext("api('/api/questions')", ctx);

  const gets = capture.filter((c) => c.url === "/api/questions" && c.method === "GET");
  assert.ok(gets.length >= 1, `应当发出 GET /api/questions，实际：${JSON.stringify(capture)}`);
  for (const g of gets) {
    assert.strictEqual(g.headers["Content-Type"], undefined, "无 body 的 GET 不应带 Content-Type");
  }
  assert.ok(dom, "页面脚本应已执行");
});

suite("带 JSON body 的 POST 会补上 Content-Type（修复未破坏写操作）", async () => {
  const capture = [];
  const { ctx } = bootPage({ script: renderInlineScript(), capture });
  await waitFor(() => capture.length >= 1, "首屏请求应已发出");

  await vm.runInContext(
    "api('/api/questions', { method: 'POST', body: JSON.stringify({title:'x'}) })",
    ctx
  );

  const posts = capture.filter((c) => c.method === "POST" && c.url === "/api/questions");
  assert.strictEqual(posts.length, 1, `应当发出 1 次 POST，实际：${JSON.stringify(capture)}`);
  assert.strictEqual(
    posts[0].headers["Content-Type"], "application/json",
    "带 JSON body 的 POST 必须补上 Content-Type: application/json"
  );
  assert.ok(posts[0].headers["X-CSRF-Token"], "所有请求都应带 CSRF 头");
});

// ── 金丝雀：证明这组测试真的能发现那个 bug（而不是永远为真的假测试）──────
suite("【金丝雀】把旧 bug 注入回去后，页面脚本必须报错", async () => {
  const buggyScript = injectPreFixBug(renderInlineScript());
  const backend = await startBackend();
  const jsErrors = [];
  const capture = [];

  // 捕获页面里 console.error 报出的错误（load() 的 catch 会写日志）
  const dom = makeDom(fs.readFileSync(TEMPLATE, "utf8"));
  const sandbox = {
    console: { log() {}, warn() {}, error: (...a) => jsErrors.push(a.join(" ")) },
    document: dom.document,
    window: { addEventListener: () => {}, location: { reload() {} } },
    sessionStorage: { getItem: () => null, setItem() {}, clear() {}, removeItem() {} },
    localStorage: { getItem: () => null, setItem() {}, clear() {} },
    setTimeout: () => 0,
    clearTimeout: () => {},
    FormData: class FormData {},
    fetch: async (url, opts) => {
      capture.push((opts && opts.method) || "GET");
      return fetch(backend.baseUrl + url, opts);
    },
  };
  sandbox.globalThis = sandbox;
  const ctx = vm.createContext(sandbox);

  try {
    vm.runInContext(buggyScript, ctx, { filename: "index.html-buggy.js" });
    // 给后台那次 load() 一点时间，让它把错误吐出来
    await new Promise((r) => setTimeout(r, 150));
  } finally {
    await backend.close();
  }

  const sawTypeError = jsErrors.some((e) => e.includes("Cannot convert undefined or null to object"));
  const sentNothing = capture.length === 0;
  assert.ok(
    sawTypeError || sentNothing,
    "注入旧 bug 后应出现 TypeError 或请求发不出去；这里通过说明测试已失去判别力（假测试）" +
    `  jsErrors=${JSON.stringify(jsErrors)} 请求数=${capture.length}`
  );
});

// ── 直接运行时的执行入口 ─────────────────────────────────────────────
if (!nodeTest) {
  (async () => {
    let failed = 0;
    console.log("前端冒烟测试（直接运行模式）\n" + "=".repeat(60));
    for (const [name, fn] of collected) {
      try {
        await fn();
        console.log("  ✔ " + name);
      } catch (e) {
        failed++;
        console.log("  ✖ " + name);
        console.log("      " + (e && e.message ? e.message.split("\n")[0] : e));
      }
    }
    console.log("=".repeat(60));
    console.log(`结果：共 ${collected.length} 项 | 通过 ${collected.length - failed} 项 | 失败 ${failed} 项`);
    process.exitCode = failed ? 1 : 0;
  })();
}
