from pydantic import BaseModel


class TransactionPublic(BaseModel):
    id: str
    sourceId: str
    sourceFileId: str
    rawTransactionId: str
    sourceRecordId: str | None = None
    transactionDate: str | None = None
    postedDate: str | None = None
    # Amounts travel as strings: JSON numbers would reintroduce float error.
    amount: str | None = None
    currency: str
    direction: str
    description: str | None = None
    reference: str | None = None
    counterparty: str | None = None
    accountIdentifier: str | None = None
    transactionType: str | None = None
    status: str
    potentialDuplicates: list[str] = []
    metadata: dict = {}
    fingerprint: str = ""
    createdAt: str | None = None
