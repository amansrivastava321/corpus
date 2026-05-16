from typing import Any, Type

from pydantic import BaseModel, ValidationError

from corpus.schemas.checkpoint import Checkpoint
from corpus.schemas.decision import ClearanceDecision
from corpus.schemas.episode import Episode, EpisodeEvent
from corpus.schemas.product import ProductHeartbeat, ProductRegistration
from corpus.schemas.signal import Signal

SCHEMA_REGISTRY: dict[str, Type[BaseModel]] = {
    "Signal": Signal,
    "ProductRegistration": ProductRegistration,
    "ProductHeartbeat": ProductHeartbeat,
    "Episode": Episode,
    "EpisodeEvent": EpisodeEvent,
    "Checkpoint": Checkpoint,
    "ClearanceDecision": ClearanceDecision,
}


class SchemaValidationError(Exception):
    def __init__(self, schema_name: str, errors: list[dict[str, Any]]) -> None:
        self.schema_name = schema_name
        self.errors = errors
        super().__init__(f"Validation failed for {schema_name}: {errors}")


class SchemaValidator:
    @staticmethod
    def validate(schema_name: str, data: dict[str, Any]) -> BaseModel:
        """Validate *data* against the named schema. Raises SchemaValidationError on failure."""
        schema_class = SCHEMA_REGISTRY.get(schema_name)
        if schema_class is None:
            raise ValueError(
                f"Unknown schema: '{schema_name}'. "
                f"Available: {list(SCHEMA_REGISTRY.keys())}"
            )
        try:
            return schema_class.model_validate(data)
        except ValidationError as exc:
            raise SchemaValidationError(schema_name, exc.errors()) from exc

    @staticmethod
    def validate_as(schema_class: Type[BaseModel], data: dict[str, Any]) -> BaseModel:
        """Validate *data* directly against a Pydantic model class."""
        try:
            return schema_class.model_validate(data)
        except ValidationError as exc:
            raise SchemaValidationError(schema_class.__name__, exc.errors()) from exc

    @staticmethod
    def is_valid(schema_name: str, data: dict[str, Any]) -> bool:
        try:
            SchemaValidator.validate(schema_name, data)
            return True
        except (SchemaValidationError, ValueError):
            return False

    @staticmethod
    def available_schemas() -> list[str]:
        return list(SCHEMA_REGISTRY.keys())
