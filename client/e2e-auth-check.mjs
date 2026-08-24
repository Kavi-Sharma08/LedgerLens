import { readFileSync } from "node:fs";
import http from "node:http";
import { chromium } from "playwright-core";
import { MongoClient } from "mongodb";

function httpRequest(method, urlStr, { body, cookie } = {}) {
  return new Promise((resolve, reject) => {
    const u = new URL(urlStr);
    const req = http.request(
      {
        hostname: u.hostname,
        port: u.port,
        path: u.pathname + u.search,
        method,
        headers: {
          ...(body ? { "content-type": "application/x-www-form-urlencoded" } : {}),
          ...(cookie ? { cookie } : {}),
        },
      },
      (res) => {
        let data = "";
        res.on("data", (c) => (data += c));
        res.on("end", () =>
          resolve({ status: res.statusCode, location: res.headers.location, setCookie: res.headers["set-cookie"] || [], body: data })
        );
      }
    );
    req.on("error", reject);
    if (body) req.write(body);
    req.end();
  });
}

const APP = "http://localhost:3000";
const API = "http://localhost:8000";
const EMAIL = "thekavisharma26@gmail.com";
const PASSWORD = "LedgerLens-E2E-2026!";

const env = Object.fromEntries(
  readFileSync(".env.local", "utf8")
    .split(/\r?\n/)
    .filter((l) => l.includes("=") && !l.trim().startsWith("#"))
    .map((l) => [l.slice(0, l.indexOf("=")).trim(), l.slice(l.indexOf("=") + 1).trim()])
);

// ---------- Resolve real identity from Atlas at runtime ----------
const mc = new MongoClient(env.MONGODB_URI);
await mc.connect();
const db = mc.db(env.MONGODB_DATABASE || "ledgerlens");
const user = await db.collection("users").findOne({ email: EMAIL });
if (!user) throw new Error("Real user not found in Atlas");
const ws = await db.collection("workspaces").findOne({ ownerId: user._id });
if (!ws) throw new Error("Workspace not found for user");
const txnCount = await db.collection("transactions").countDocuments({ workspaceId: ws._id });
const runCount = await db.collection("reconciliation_runs").countDocuments({ workspaceId: ws._id });
const excCount = await db.collection("exceptions").countDocuments({ workspaceId: ws._id });
await mc.close();

console.log(`[atlas] userId=${user._id} workspaceId=${ws._id}`);
console.log(`[atlas] txns=${txnCount} runs=${runCount} exceptions=${excCount}`);

let failures = [];
function safeJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}
function check(name, ok, detail = "") {
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "   -- " + detail : ""}`);
  if (!ok) failures.push(name);
}

const browser = await chromium.launch({ channel: "chrome", headless: true });

try {
  // ================= Check 1: logged-out protection =================
  {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    await page.goto(APP + "/dashboard", { waitUntil: "domcontentloaded" });
    await page.waitForURL("**/login**", { timeout: 15000 }).catch(() => {});
    check(
      "1a. /dashboard redirects to /login when logged out",
      page.url().includes("/login"),
      "landed=" + page.url()
    );
    const status = await page.evaluate(() =>
      fetch("/api/backend/api/overview").then((r) => r.status).catch(() => 0)
    );
    check("1b. proxy blocks financial data when logged out", status === 401, "status=" + status);
    const direct = await fetch(API + "/api/workspaces/current").then((r) => r.status).catch(() => 0);
    check("1c. FastAPI rejects untrusted direct call", direct === 401, "status=" + direct);
    await ctx.close();
  }

  // ================= Check 2: Google OAuth initiation =================
  {
    // Auth.js answers provider sign-in with a cross-origin redirect, which
    // browser fetch cannot follow; a raw HTTP exchange captures it directly.
    const csrfRes = await httpRequest("GET", APP + "/api/auth/csrf");
    const csrfCookie = csrfRes.setCookie.map((c) => c.split(";")[0]).join("; ");
    const csrfToken = JSON.parse(csrfRes.body).csrfToken;
    const post = await httpRequest(
      "POST",
      APP + "/api/auth/signin/google",
      {
        cookie: csrfCookie,
        body: new URLSearchParams({ csrfToken, callbackUrl: APP + "/", json: "true" }).toString(),
      }
    );
    const url =
      post.location ?? (post.body ? safeJson(post.body)?.url ?? "" : "");
    const oauthOk =
      [200, 302].includes(post.status) &&
      url.includes("accounts.google.com") &&
      url.includes("client_id=");
    const hasState = url.includes("state=");
    check(
      "2. Google OAuth initiation issues accounts.google.com authorize URL",
      oauthOk && hasState,
      `status=${post.status} client_id=${url.includes("client_id=")} state=${hasState} full=${url}`
    );
    // Full consent screen requires interactive Google credentials; everything
    // downstream of session issuance is proven below via the credentials
    // provider, which flows through the identical Auth.js machinery.
  }

  // ================= Checks 3-11: authenticated flow =================
  const ctx = await browser.newContext();
  const page = await ctx.newPage();

  const backendCalls = [];
  page.on("response", (r) => {
    if (r.url().includes("/api/backend/")) backendCalls.push({ url: r.url(), status: r.status() });
  });

  await page.goto(APP + "/login", { waitUntil: "domcontentloaded" });
  await page.fill("#email", EMAIL);
  await page.fill('input[name="password"]', PASSWORD);
  const authResponses = [];
  page.on("response", (r) => {
    if (r.url().includes("/api/auth/")) authResponses.push(`${r.request().method()} ${r.url().replace(APP, "")} -> ${r.status()}`);
  });
  await Promise.all([
    page.waitForURL("**/dashboard**", { timeout: 30000 }).catch(() => {}),
    page.click('button[type="submit"]'),
  ]);
  if (!page.url().includes("/dashboard")) {
    // Diagnostics: what did the UI say?
    const alertText = await page
      .locator('[role="alert"]')
      .allInnerTexts()
      .catch(() => []);
    console.log("[debug] still on:", page.url());
    console.log("[debug] alerts:", JSON.stringify(alertText));
    console.log("[debug] auth calls:", authResponses.join(" | ") || "(none)");
    const sessionNow = await page.evaluate(() =>
      fetch("/api/auth/session").then((r) => r.json())
    );
    console.log("[debug] session after submit:", JSON.stringify(sessionNow));
    throw new Error("Login did not reach /dashboard");
  }
  check("login form -> /dashboard", true, page.url());

  // Check 3: Auth.js session identity matches Atlas user exactly
  const sess = await page.evaluate(() => fetch("/api/auth/session").then((r) => r.json()));
  check(
    "3. Auth.js session carries correct app identity",
    sess?.user?.id === String(user._id) &&
      sess?.user?.email === user.email &&
      sess?.user?.name === user.name,
    `session.id=${sess?.user?.id} expected=${user._id}`
  );

  // Check 4+5: proxy forwarded a request that FastAPI accepted with THIS identity
  const proxiedWs = await page.evaluate(() =>
    fetch("/api/backend/api/workspaces/current").then(async (r) => ({ status: r.status, body: await r.json().catch(() => null) }))
  );
  check("4/5a. proxy->FastAPI accepted authenticated call", proxiedWs.status === 200, "status=" + proxiedWs.status);
  check(
    "4/5b. FastAPI resolved the correct user's workspace",
    proxiedWs.body && String(proxiedWs.body.ownerId) === String(user._id),
    `ownerId=${proxiedWs.body?.ownerId}`
  );

  // Security probe: spoofed trusted headers must be ignored by the proxy
  const spoof = await page.evaluate(() =>
    fetch("/api/backend/api/workspaces/current", {
      headers: { "X-LL-User-Id": "000000000000000000000000", "X-LL-Internal-Secret": "evil" },
    }).then(async (r) => ({ status: r.status, body: await r.json().catch(() => null) }))
  );
  check(
    "5c. proxy overrides spoofed X-LL-* headers",
    spoof.status === 200 && String(spoof.body?.ownerId) === String(user._id),
    "status=" + spoof.status
  );

  // Check 7 (+6): switcher shows the resolved workspace name
  const summarySection = page.locator('[aria-label="Workspace summary"]');
  await summarySection.waitFor({ timeout: 20000 });
  const switcher = await page.locator('[aria-label^="Workspace:"]').innerText();
  check(
    "7. switcher shows 'Kavi Sharma's Workspace', not 'No workspace'",
    switcher.includes(ws.name) && !switcher.includes("No workspace"),
    JSON.stringify(switcher.replace(/\s+/g, " "))
  );

  // Check 9: overview KPIs from real data
  const kpiText = (await summarySection.innerText()).replace(/,/g, "");
  check("9a. overview shows real transaction count (" + txnCount + ")", kpiText.includes(String(txnCount)), kpiText.replace(/\s+/g, " ").slice(0, 120));
  const pageText = (await page.locator("main").innerText()).replace(/\s+/g, " ");
  check("9b. overview lists recent reconciliations section", pageText.includes("Recent reconciliations"));
  check("9c. completed run visible on overview", /completed/i.test(pageText));

  // Check 8: transactions load from Atlas into the table
  let txnApiCount = -1;
  page.on("response", async (r) => {
    if (r.url().includes("/api/backend/api/transactions") && r.request().method() === "GET") {
      try {
        const j = await r.json();
        txnApiCount = j.items?.length ?? -1;
      } catch {}
    }
  });
  await page.goto(APP + "/dashboard/transactions", { waitUntil: "domcontentloaded" });
  await page.waitForSelector("table tbody tr", { timeout: 20000 });
  await page.waitForTimeout(500);
  const rows = await page.locator("table tbody tr").count();
  check("8a. transactions table renders rows from Atlas", rows > 0, "rows=" + rows);
  check("8b. rendered rows match API page size", rows === txnApiCount, `ui=${rows} api=${txnApiCount}`);

  // Check 10: reconciliations list shows the seeded run as Completed
  await page.goto(APP + "/dashboard/reconciliations", { waitUntil: "domcontentloaded" });
  await page.waitForSelector("table tbody tr", { timeout: 20000 });
  const reconText = (await page.locator("main").innerText()).replace(/\s+/g, " ");
  check("10. reconciliations list shows Completed run", reconText.includes("Completed") && (await page.locator("table tbody tr").count()) >= runCount, `runs=${runCount}`);

  // Check 11: exceptions load
  await page.goto(APP + "/dashboard/exceptions", { waitUntil: "domcontentloaded" });
  await page.waitForSelector("table tbody tr", { timeout: 20000 });
  const excRows = await page.locator("table tbody tr").count();
  check("11. exceptions table renders rows", excRows > 0, "rows=" + excRows);

  // Every proxied call during the whole session must have succeeded
  const bad = backendCalls.filter((c) => c.status >= 400);
  check(
    "4/5d. all /api/backend calls returned 2xx",
    backendCalls.length > 0 && bad.length === 0,
    `${backendCalls.length} calls, failures=${bad.length}`
  );

  // ================= Check 12: logout invalidates access =================
  await page.click('[aria-label="Open account menu"]');
  await page.click("text=Sign out");
  await page.waitForURL("**/login**", { timeout: 20000 });
  check("12a. sign out returns to /login", page.url().includes("/login"));

  const postLogout = await page.evaluate(() =>
    fetch("/api/backend/api/overview").then((r) => r.status).catch(() => 0)
  );
  check("12b. financial data blocked again after logout", postLogout !== 200, "status=" + postLogout);

  await page.goto(APP + "/dashboard", { waitUntil: "domcontentloaded" });
  await page.waitForURL("**/login**", { timeout: 15000 }).catch(() => {});
  check("12c. /dashboard redirects to login after logout", page.url().includes("/login"));

  await ctx.close();
} finally {
  await browser.close();
}

console.log("\n==== RESULT:", failures.length === 0 ? "ALL CHECKS PASSED" : `${failures.length} FAILURES`, "====");
process.exit(failures.length === 0 ? 0 : 1);
