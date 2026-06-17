class ServiceRegistry:
    """A clean Dependency Injection Registry to locate registered external services.
    Enforces decoupling so production code never imports mocks directly.
    """
    _services = {}

    @classmethod
    def register(cls, name: str, service_instance):
        cls._services[name] = service_instance

    @classmethod
    def get(cls, name: str):
        if name not in cls._services:
            raise KeyError(f"Service '{name}' is not registered in the ServiceRegistry.")
        return cls._services[name]

    @classmethod
    def clear(cls):
        cls._services.clear()
