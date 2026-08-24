import { readFileSync } from "node:fs";
import bcrypt from "bcryptjs";
import { MongoClient } from "mongodb";

const env = Object.fromEntries(
  readFileSync(".env.local", "utf8")
    .split(/\r?\n/)
    .filter((l) => l.includes("=") && !l.trim().startsWith("#"))
    .map((l) => [l.slice(0, l.indexOf("=")).trim(), l.slice(l.indexOf("=") + 1).trim()])
);

const mc = new MongoClient(env.MONGODB_URI);
await mc.connect();
const db = mc.db(env.MONGODB_DATABASE || "ledgerlens");
const u = await db.collection("users").findOne({ email: "thekavisharma26@gmail.com" });
console.log("hash prefix:", u.passwordHash?.slice(0, 7), "| len:", u.passwordHash?.length);
const ok = await bcrypt.compare("LedgerLens-E2E-2026!", u.passwordHash);
console.log("bcrypt.compare ->", ok);
await mc.close();
