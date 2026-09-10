class AppError(Exception):
    """A public error whose message is safe to return to an agent."""

    def __init__(self, code: str, message: str, exit_code: int, *, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code
        self.retryable = retryable

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
        }
