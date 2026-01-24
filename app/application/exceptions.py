class LLMUpstreamError(RuntimeError):
    """Raised when LLM provider fails (timeouts, network errors, service unavailable)."""
    pass


class LLMContractError(RuntimeError):
    """Raised when LLM adapter violates contract (bad format or missing data)."""
    pass
