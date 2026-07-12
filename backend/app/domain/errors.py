class DomainError(Exception):
    code = "domain_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
