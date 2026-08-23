import { MongoClient } from "mongodb";

/**
 * Shared MongoDB client for the Next.js server (Auth.js adapter, registration,
 * credentials validation). Auth data lives here; FastAPI reads the same
 * database for business data but never manages authentication.
 */

if (!process.env.MONGODB_URI) {
  throw new Error(
    "MONGODB_URI is not set. Add it to client/.env.local (see .env.example)."
  );
}

const uri = process.env.MONGODB_URI;

let client;
let clientPromise;

if (process.env.NODE_ENV === "development") {
  // Reuse one client across hot reloads; a fresh client per module evaluation
  // would exhaust the connection pool.
  const globalWithMongo = globalThis;
  if (!globalWithMongo._ledgerLensMongoPromise) {
    client = new MongoClient(uri);
    globalWithMongo._ledgerLensMongoPromise = client.connect();
  }
  clientPromise = globalWithMongo._ledgerLensMongoPromise;
} else {
  client = new MongoClient(uri);
  clientPromise = client.connect();
}

export default clientPromise;

export async function getAuthDatabase() {
  const client = await clientPromise;
  return client.db(process.env.MONGODB_DATABASE || "ledgerlens");
}
