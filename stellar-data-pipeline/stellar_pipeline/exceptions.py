"""Custom exception hierarchy for the stellar data pipeline."""


class PipelineError(Exception):
    """Base exception for all pipeline errors."""


class ConfigError(PipelineError):
    """Raised when configuration is invalid or missing."""


class ExtractionError(PipelineError):
    """Raised when data extraction from the TAP API fails."""


class ValidationError(PipelineError):
    """Raised when data validation fails."""


class TransformError(PipelineError):
    """Raised when data transformation fails."""


class LoadError(PipelineError):
    """Raised when loading data into the database fails."""
