from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class Source(BaseModel):
    key_quote: str
    link: str


class DataSummary(BaseModel):
    available: bool
    summary: str
    sources: List[Source]


class ESGData(BaseModel):
    scope_1: DataSummary
    scope_2: DataSummary
    scope_3: DataSummary
    ecovadis: DataSummary
    reduction_targets: Optional[DataSummary]
    iso_14001: DataSummary
    product_lca: DataSummary
    segment: str
    updated: datetime


class Supplier(BaseModel):
    id: str
    name: str
    website: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    esg: ESGData


class AgentSupplier(BaseModel):
    name: str
    website: Optional[str] = None
    description: Optional[str] = None