import uuid

from pydantic import BaseModel


class HouseholdSettingsRead(BaseModel):
    id: uuid.UUID
    correggi_orientamento: bool

    model_config = {"from_attributes": True}


class HouseholdSettingsUpdate(BaseModel):
    correggi_orientamento: bool
