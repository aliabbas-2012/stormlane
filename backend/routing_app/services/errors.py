class ServiceError(Exception):
    """A request that is well-formed but cannot be served (e.g. beyond the forecast horizon).
    The API layer maps it to {"error": {code, message}} with `http_status`."""

    def __init__(self, code: str, message: str, http_status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
