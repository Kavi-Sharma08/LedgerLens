import os, urllib.parse, requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

SECRET = os.environ['INTERNAL_API_SECRET']
MONGODB_URI = os.environ['MONGODB_URI']
MONGODB_DATABASE = os.environ['MONGODB_DATABASE']

client = MongoClient(MONGODB_URI)
db = client[MONGODB_DATABASE]
user = db.users.find_one({"email": "thekavisharma26@gmail.com"})
if not user:
    raise SystemExit("User not found!")
user_id = str(user['_id'])
print(f"User ID: {user_id}")

base = "http://localhost:8000"
headers = {
    "X-LL-User-Id": user_id,
    "X-LL-User-Email": urllib.parse.quote("thekavisharma26@gmail.com"),
    "X-LL-Internal-Secret": SECRET,
    "X-LL-Workspace-Id": "6a8d742a3a5477b2a74477a6",
}

def section(title):
    print(f"\n{'='*60}\n{title}\n{'='*60}")

# 1. GET /api/transactions?limit=5
section("TEST 1: GET /api/transactions?limit=5 (with workspace header)")
r = requests.get(f"{base}/api/transactions?limit=5", headers=headers)
print(f"Status: {r.status_code}")
data = r.json()
items = data.get("items", data.get("data", []))
print(f"Number of items returned: {len(items)}")
if items:
    first = items[0]
    print(f"First item keys: {list(first.keys())}")
    print(f"  _id:        {first.get('_id')}")
    print(f"  date:       {first.get('date')}")
    print(f"  amount:     {first.get('amount')}")
    print(f"  description:{first.get('description')}")
    print(f"  workspaceId:{first.get('workspaceId')}")
    first_id = first.get('_id')
else:
    first_id = None

# 2. Without workspace header (should fail)
section("TEST 2: GET /api/transactions?limit=5 (NO workspace header)")
no_ws = {k: v for k, v in headers.items() if k != "X-LL-Workspace-Id"}
r2 = requests.get(f"{base}/api/transactions?limit=5", headers=no_ws)
print(f"Status: {r2.status_code}")
print(f"Response: {r2.text[:500]}")

# 3. GET /api/transactions/{id}
if first_id:
    section(f"TEST 3: GET /api/transactions/{first_id}")
    r3 = requests.get(f"{base}/api/transactions/{first_id}", headers=headers)
    print(f"Status: {r3.status_code}")
    d3 = r3.json() if r3.status_code == 200 else r3.text
    if isinstance(d3, dict):
        print(f"  _id:        {d3.get('_id')}")
        print(f"  date:       {d3.get('date')}")
        print(f"  amount:     {d3.get('amount')}")
    else:
        print(f"Response: {d3[:500]}")

# 4. GET /api/sources?limit=5
section("TEST 4: GET /api/sources?limit=5")
r4 = requests.get(f"{base}/api/sources?limit=5", headers=headers)
print(f"Status: {r4.status_code}")
print(f"Response: {r4.text[:1000]}")

# 5. Check workspaceId types in transactions collection
section("TEST 5: workspaceId type check in transactions collection")
sample = list(db.transactions.find().limit(20))
from bson import ObjectId
type_counts = {}
for doc in sample:
    wid = doc.get('workspaceId')
    t = type(wid).__name__
    type_counts[t] = type_counts.get(t, 0) + 1
    if t != 'ObjectId' and wid is not None:
        print(f"  Non-ObjectId workspaceId found: {wid!r} (type={t}) in doc _id={doc.get('_id')}")
print(f"\nType distribution in sample of {len(sample)} docs: {type_counts}")
total = db.transactions.estimated_document_count()
print(f"Total documents in transactions: {total}")
non_oid = db.transactions.count_documents({"workspaceId": {"$type": "string"}})
print(f"Documents where workspaceId is a string (not ObjectId): {non_oid}")

print("\nDone.")
